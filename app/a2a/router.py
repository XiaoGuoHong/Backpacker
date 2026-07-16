from app.a2a.messages import A2AError, A2ARequest, A2AResponse
from app.a2a.transport import HttpA2AConnection
from app.core.config import Settings
from app.observability.logging import log_event


class A2ARouter:
    """task_type → Agent URL 映射，统一错误转换。"""

    def __init__(self, settings: Settings, http: HttpA2AConnection | None = None):
        self.settings = settings
        self.http = http or HttpA2AConnection(timeout_ms=settings.a2a_timeout_ms)
        self._mapping = {
            "attraction": settings.attraction_agent_url,
            "weather": settings.weather_agent_url,
            "hotel": settings.hotel_agent_url,
        }

    def resolve(self, task_type: str) -> str | None:
        return self._mapping.get(task_type)

    async def dispatch(self, request: A2ARequest) -> A2AResponse:
        url = self.resolve(request.task_type)
        if not url:
            log_event("a2a_router_unknown", task_id=request.task_id, agent_type=request.task_type,
                      status="failed", error_code="E_INTENT_UNKNOWN")
            return A2AResponse(
                task_id=request.task_id,
                status="failed",
                error=A2AError(code="E_INTENT_UNKNOWN", message=f"未知 task_type: {request.task_type}"),
            )
        return await self.http.post(url, request)

    async def close(self) -> None:
        await self.http.close()
