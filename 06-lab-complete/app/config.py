"""Read deploy-time settings from the environment."""
import os
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Settings:
    port: int
    environment: str
    agent_api_key: str
    redis_url: str
    rate_limit_per_minute: int
    budget_period: str
    budget_usd: Decimal

    @classmethod
    def from_environment(cls) -> "Settings":
        port = int(os.getenv("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535")

        rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
        if rate_limit < 1:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be positive")

        daily_budget = os.getenv("DAILY_BUDGET_USD", "").strip()
        budget = Decimal(daily_budget or os.getenv("MONTHLY_BUDGET_USD") or "10")
        if not budget.is_finite() or budget < 0:
            raise ValueError("The configured budget must be finite and non-negative")

        return cls(
            port=port,
            environment=os.getenv("ENVIRONMENT", "development"),
            agent_api_key=os.getenv("AGENT_API_KEY", ""),
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            rate_limit_per_minute=rate_limit,
            budget_period="day" if daily_budget else "month",
            budget_usd=budget,
        )


settings = Settings.from_environment()
