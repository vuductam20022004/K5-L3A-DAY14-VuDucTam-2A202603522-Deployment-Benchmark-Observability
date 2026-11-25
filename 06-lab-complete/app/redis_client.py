"""Redis client for readiness, rate limits and budgets."""
import redis
from redis.exceptions import RedisError

from app.config import settings


r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=2,
)


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except RedisError:
        return False
