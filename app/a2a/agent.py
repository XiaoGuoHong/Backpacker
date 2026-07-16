from datetime import datetime, timezone
from typing import Any

from app.a2a.messages import A2ARequest, A2AResponse, A2AError
from app.a2a.server import A2AServer
from app.a2a.transport import now
from app.core.config import Settings
from app.mcp.connection import MCPConnection, StreamableHttpMCPConnection


class SpecialistAgent(A2AServer):
    """专业 Agent Server：通过 MCP 调用 Amap MCP Server 的工具。"""

    def __init__(
        self,
        name: str,
        task_type: str,
        tool_name: str,
        settings: Settings,
        mcp: MCPConnection | None = None,
    ):
        super().__init__(name, [task_type], settings)
        self.task_type = task_type
        self.tool_name = tool_name
        self._mcp = mcp

    def _mcp_connection(self) -> MCPConnection:
        if self._mcp is None:
            self._mcp = StreamableHttpMCPConnection(self.settings.amap_mcp_url)
        return self._mcp

    async def handle(self, request: A2ARequest) -> A2AResponse:
        mcp = self._mcp_connection()
        result = await mcp.call(self.tool_name, request.params)
        if result.status == "success":
            return A2AResponse(
                task_id=request.task_id,
                status="success",
                result=result.content,
                source=result.source,
                updated_at=result.fetched_at or now(),
            )
        if result.status == "timeout":
            return A2AResponse(
                task_id=request.task_id,
                status="timeout",
                error=A2AError(code="E_TOOL_TIMEOUT", message="工具超时"),
            )
        return A2AResponse(
            task_id=request.task_id,
            status="failed",
            error=A2AError(code=result.error_code or "E_TOOL_UNAVAILABLE", message="工具不可用"),
        )

    async def health(self) -> dict[str, Any]:
        data = await super().health()
        try:
            ok = True
            # 简单探测 MCP 是否可连接
            mcp = self._mcp_connection()
            defs = mcp.definitions()
            data["mcp_tools"] = [d.name for d in defs]
        except Exception:
            ok = False
            data["mcp_tools"] = []
        data["mcp_available"] = ok
        return data


def create_attraction_agent(settings: Settings, mcp: MCPConnection | None = None) -> SpecialistAgent:
    return SpecialistAgent(
        name="AttractionSearchAgent",
        task_type="attraction",
        tool_name="amap_poi_search",
        settings=settings,
        mcp=mcp,
    )


def create_weather_agent(settings: Settings, mcp: MCPConnection | None = None) -> SpecialistAgent:
    return SpecialistAgent(
        name="WeatherQueryAgent",
        task_type="weather",
        tool_name="weather_tool",
        settings=settings,
        mcp=mcp,
    )


def create_hotel_agent(settings: Settings, mcp: MCPConnection | None = None) -> SpecialistAgent:
    return SpecialistAgent(
        name="HotelAgent",
        task_type="hotel",
        tool_name="amap_poi_search",
        settings=settings,
        mcp=mcp,
    )
