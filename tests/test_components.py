from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.models import TripRequest
from app.gateway.ratelimit import RateLimiter
from app.gateway.validation import validate_raw_input, validate_trip_request
from datetime import date


def test_validate_raw_input_strips_and_passes():
    s = validate_raw_input("  北京天气  ", Settings())
    assert s == "北京天气"


def test_validate_raw_input_rejects_none():
    try:
        validate_raw_input(None, Settings())
        assert False, "expected AppError"
    except AppError as e:
        assert e.code == ErrorCode.INVALID_INPUT


def test_validate_raw_input_rejects_overlong():
    try:
        validate_raw_input("a" * 600, Settings(max_input_length=512))
        assert False, "expected AppError"
    except AppError as e:
        assert e.code == ErrorCode.INVALID_INPUT


def test_validate_trip_request_passes():
    req = TripRequest(
        destination="北京",
        start_date=date(2025, 8, 11),
        days=2,
        budget_level="mid",
        interests=["历史文化"],
        hotel_type="舒适型",
    )
    assert validate_trip_request(req, Settings()) is req


def test_validate_trip_request_rejects_too_long_destination():
    req = TripRequest(
        destination="北" * 10,
        start_date=date(2025, 8, 11),
        days=2,
        budget_level="mid",
        interests=["历史文化"],
        hotel_type="舒适型",
    )
    try:
        validate_trip_request(req, Settings(max_input_length=5))
        assert False, "expected AppError"
    except AppError as e:
        assert e.code == ErrorCode.INVALID_INPUT


def test_ratelimit_allows_within_limit_then_blocks():
    limiter = RateLimiter(limit_per_minute=3)
    assert limiter.is_allowed("ip1") is True
    assert limiter.is_allowed("ip1") is True
    assert limiter.is_allowed("ip1") is True
    assert limiter.is_allowed("ip1") is False
    limiter.reset("ip1")
    assert limiter.is_allowed("ip1") is True


def test_ratelimit_isolated_per_key():
    limiter = RateLimiter(limit_per_minute=1)
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("a") is False
    assert limiter.is_allowed("b") is True


def test_http_a2a_connection_unreachable():
    import anyio
    from app.a2a.transport import HttpA2AConnection
    from app.a2a.messages import A2ARequest

    async def run():
        conn = HttpA2AConnection(timeout_ms=500)
        req = A2ARequest(request_id="r1", task_id="t1", task_type="weather")
        resp = await conn.post("http://127.0.0.1:1/tasks/send", req)
        assert resp.status in ("failed", "timeout")
        assert resp.error is not None
        await conn.close()

    anyio.run(run)