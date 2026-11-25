"""Reserve and settle mock LLM costs in a shared Redis budget."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = Decimal("0.00015")
PRICE_OUTPUT_PER_1K = Decimal("0.0006")
NANO_USD_PER_USD = 1_000_000_000


# Integer amounts in billionths of a dollar represent both prices exactly.
_reserve_budget = r.register_script("""
if redis.call('HEXISTS', KEYS[1], ARGV[1]) == 1 then
    return 1
end
local total = tonumber(redis.call('HGET', KEYS[1], 'total') or '0')
if total + tonumber(ARGV[2]) > tonumber(ARGV[3]) then
    return 0
end
redis.call('HINCRBY', KEYS[1], 'total', ARGV[2])
redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[4])
return 1
""")


# The reservation field makes settling a retried operation idempotent.
_settle_budget = r.register_script("""
local reserved = redis.call('HGET', KEYS[1], ARGV[1])
if reserved then
    redis.call('HINCRBY', KEYS[1], 'total', tonumber(ARGV[2]) - tonumber(reserved))
    redis.call('HDEL', KEYS[1], ARGV[1])
end
return 0
""")


@dataclass(frozen=True)
class BudgetReservation:
    period_key: str
    request_id: str


def estimate_tokens(text: str) -> int:
    """Estimate usage for the mock model at four characters per token."""
    return max(1, (len(text) + 3) // 4)


def _cost_nano_usd(input_tokens: int, output_tokens: int) -> int:
    price = input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K
    return int(price * (NANO_USD_PER_USD // 1000))


def check_budget(input_tokens: int, max_output_tokens: int) -> BudgetReservation:
    now = datetime.now(timezone.utc)
    daily = settings.budget_period == "day"
    period = now.strftime("%Y-%m-%d" if daily else "%Y-%m")
    reservation = BudgetReservation(f"day14:budget:{settings.budget_period}:{period}", uuid4().hex)
    allowed = _reserve_budget(
        keys=[reservation.period_key],
        args=[
            reservation.request_id,
            _cost_nano_usd(input_tokens, max_output_tokens),
            int(settings.budget_usd * NANO_USD_PER_USD),
            (2 if daily else 35) * 86400,
        ],
    )
    if not allowed:
        raise HTTPException(status_code=402, detail="LLM budget exceeded")
    return reservation


def record_cost(input_tokens: int, output_tokens: int, reservation: BudgetReservation) -> float:
    cost = _cost_nano_usd(input_tokens, output_tokens)
    _settle_budget(keys=[reservation.period_key], args=[reservation.request_id, cost])
    return cost / NANO_USD_PER_USD


def release_budget(reservation: BudgetReservation) -> None:
    _settle_budget(keys=[reservation.period_key], args=[reservation.request_id, 0])
