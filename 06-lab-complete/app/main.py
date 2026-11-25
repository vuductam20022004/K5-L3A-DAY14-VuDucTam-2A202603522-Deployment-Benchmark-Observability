"""Production AI agent for Part 6."""
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_tokens, record_cost, release_budget
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import MOCK_RESPONSES, ask as llm_ask

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

MAX_MOCK_OUTPUT_TOKENS = max(
    estimate_tokens(answer) for responses in MOCK_RESPONSES.values() for answer in responses
)


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "event": event,
        **fields,
    }, ensure_ascii=False))


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("startup", environment=settings.environment)
    try:
        yield
    finally:
        r.close()
        log_event("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_request(request: Request, call_next):
    start = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        log_event("request", method=request.method, route=route, status=status,
                  latency_ms=round((perf_counter() - start) * 1000, 1))


@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, exc: RedisError):
    return JSONResponse(status_code=503, content={"detail": "Redis is unavailable"})


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis is unavailable")
    return {"ready": True}


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    input_tokens = estimate_tokens(body.question)
    reservation = check_budget(input_tokens, MAX_MOCK_OUTPUT_TOKENS)
    try:
        answer = llm_ask(body.question)
    except Exception:
        try:
            release_budget(reservation)
        except RedisError:
            log_event("budget_release_failed")
        raise

    output_tokens = estimate_tokens(answer)
    cost = record_cost(input_tokens, output_tokens, reservation)
    log_event("llm_usage", input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost)
    return {"question": body.question, "answer": answer}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, workers=2)
