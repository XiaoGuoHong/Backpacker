from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode
from app.core.models import HealthResponse, TripRequest
from app.gateway.ratelimit import RateLimiter
from app.gateway.security import is_suspicious
from app.gateway.validation import validate_trip_request
from app.observability.metrics import metrics
from app.orchestrator.service import OrchestratorService

router = APIRouter()


def get_service(request: Request) -> OrchestratorService:
    return request.app.state.orchestrator_service


def get_settings_dep() -> Settings:
    return get_settings()


def _client_ip(request: Request) -> str:
    if request.client is None:
        return request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
    return request.client.host


@router.post("/api/v1/plan")
async def plan_endpoint(
    req: TripRequest,
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    service: OrchestratorService = Depends(get_service),
):
    request_id = request.state.request_id
    ip = _client_ip(request)

    if not request.app.state.rate_limiter.is_allowed(ip):
        raise AppError(
            ErrorCode.RATE_LIMITED,
            "rate limited",
            status_code=429,
            public_detail="请求过于频繁，请稍后重试",
        )

    validate_trip_request(req, settings)

    if is_suspicious(req.destination) or any(is_suspicious(i) for i in req.interests):
        raise AppError(
            ErrorCode.INVALID_INPUT,
            "suspicious input detected",
            status_code=400,
            public_detail="输入包含不支持的指令，请使用自然语言描述您的需求。",
        )

    result = await service.plan(req, request_id)
    return JSONResponse(result)


@router.get("/api/v1/plan/{task_id}/events")
async def plan_events(
    task_id: str,
    request: Request,
    service: OrchestratorService = Depends(get_service),
):
    async def event_generator():
        async for event in service.subscribe_events(task_id):
            yield event

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/v1/plan/{task_id}")
async def plan_result(
    task_id: str,
    service: OrchestratorService = Depends(get_service),
):
    result = service.get_result(task_id)
    if result is None:
        raise AppError(
            ErrorCode.NOT_FOUND,
            "task not found",
            status_code=404,
            public_detail="任务不存在或已过期",
        )
    return JSONResponse(result)


@router.get("/metrics")
async def metrics_endpoint():
    return metrics.snapshot()


@router.get("/api/v1/config")
async def client_config(settings: Settings = Depends(get_settings_dep)):
    return {
        "amap_js_key": settings.amap_js_key,
        "has_amap_js_key": bool(settings.amap_js_key),
    }


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    service: OrchestratorService = Depends(get_service),
):
    dep = await service.health()
    status = "ok" if dep.available else "degraded"
    return HealthResponse(
        status=status,
        app={"alive": True, "name": settings.app_name, "env": settings.environment},
        dependencies=[dep],
        timestamp=datetime.now(timezone.utc),
    )
