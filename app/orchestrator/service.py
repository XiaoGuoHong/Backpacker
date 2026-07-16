import asyncio
import time
import uuid
import datetime
from datetime import datetime as _datetime, timezone
from typing import Any, AsyncGenerator

from app.a2a.client import A2AClient
from app.a2a.messages import A2AResponse
from app.core.config import Settings
from app.core.errors import ErrorCode
from app.core.models import (
    Attraction,
    DailyWeather,
    DependencyHealth,
    GeoPoint,
    HealthResponse,
    Hotel,
    Itinerary,
    TripRequest,
)
from app.mcp.connection import InProcessMCPConnection, StreamableHttpMCPConnection
from app.mcp.registry import build_default_registry
from app.mcp.tool import MCPRegistry
from app.observability.logging import log_event, request_id_var
from app.observability.metrics import metrics
from app.orchestrator.agent import DispatchResult, OrchestratorAgent
from app.orchestrator.planner import PlannerAgent
from app.orchestrator.session import SessionStore


class OrchestratorService:
    def __init__(
        self,
        client: A2AClient,
        agent: OrchestratorAgent,
        planner: PlannerAgent,
        session_store: SessionStore,
        mcp: MCPRegistry,
        settings: Settings,
    ):
        self.client = client
        self.agent = agent
        self.planner = planner
        self.session_store = session_store
        self.mcp = mcp
        self.settings = settings
        self._events: dict[str, asyncio.Queue[str]] = {}
        self._results: dict[str, dict[str, Any]] = {}

    async def plan(self, request: TripRequest, request_id: str) -> dict[str, Any]:
        request_id_var.set(request_id)
        task_id = f"plan-{uuid.uuid4().hex[:12]}"
        self._events[task_id] = asyncio.Queue()
        self._emit(task_id, "received", "收到行程规划请求")
        asyncio.create_task(self._run_plan(task_id, request, request_id))
        return {"task_id": task_id, "request_id": request_id, "status": "accepted"}

    def _emit(self, task_id: str, stage: str, message: str) -> None:
        queue = self._events.get(task_id)
        if queue is None:
            return
        data = f"event: {stage}\ndata: {message}\n\n"
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            pass

    async def _run_plan(self, task_id: str, request: TripRequest, request_id: str) -> None:
        request_id_var.set(request_id)
        start = time.monotonic()
        try:
            self._emit(task_id, "searching_attractions", "正在搜索景点…")

            items: list[tuple[str, dict]] = [
                ("attraction", {"keywords": "景点", "city": request.destination}),
                ("weather", {"city": request.destination, "start_date": request.start_date.isoformat(), "days": request.computed_days}),
                ("hotel", {"keywords": "酒店", "city": request.destination, "type": "100000"}),
            ]

            dispatch_results = await self.agent.dispatch_multi(items, request_id)

            self._emit(task_id, "enriching", "正在为景点补充图片…")
            attractions = self._parse_attractions(dispatch_results)
            hotels = self._parse_hotels(dispatch_results)
            weathers = self._parse_weather(dispatch_results)

            # 为每个景点补图
            for attraction in attractions:
                image_url = await self._fetch_image(attraction.name)
                if image_url:
                    attraction.image_url = image_url

            self._emit(task_id, "planning", "正在规划行程…")
            itinerary = await self.planner.integrate(attractions, hotels, weathers, request)

            # 记录部分失败
            notes = list(itinerary.notes)
            failed = [dr.task_type for dr in dispatch_results if dr.response.status != "success"]
            if failed:
                notes.append(f"以下数据源暂不可用：{', '.join(failed)}，已使用可用数据生成行程。")

            duration_ms = round((time.monotonic() - start) * 1000, 1)
            metrics.record("plan", "success" if not failed else "partial", duration_ms)
            log_event("plan_complete", request_id=request_id, task_id=task_id,
                      status="success" if not failed else "partial", duration_ms=duration_ms)

            result = {
                "request_id": request_id,
                "task_id": task_id,
                "status": "success" if not failed else "partial",
                "itinerary": itinerary.model_dump(mode="json"),
                "condition_summary": f"{request.destination} {request.computed_days} 日行程（{request.start_date.isoformat()} 起）",
                "query_time": _datetime.now(timezone.utc).isoformat(),
                "hints": "数据仅供参考，具体以官方发布为准。",
            }
            self._results[task_id] = result
            self.session_store.save_plan(request_id, task_id, request, itinerary)
            self._emit(task_id, "completed", "行程规划完成")
        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            metrics.record("plan", "failed", duration_ms)
            log_event("plan_failed", request_id=request_id, task_id=task_id,
                      status="failed", duration_ms=duration_ms, error_code="E_UPSTREAM_UNAVAILABLE")
            self._results[task_id] = {
                "request_id": request_id,
                "task_id": task_id,
                "status": "failed",
                "error_code": "E_UPSTREAM_UNAVAILABLE",
                "error_message": "行程规划失败，请稍后重试。",
            }
            self._emit(task_id, "failed", "行程规划失败")

    def _parse_attractions(self, results: list[DispatchResult]) -> list[Attraction]:
        for dr in results:
            if dr.task_type == "attraction" and dr.response.status == "success":
                items = dr.response.result.get("items") or []
                out = []
                for item in items[: self.settings.max_results]:
                    loc = item.get("location")
                    out.append(Attraction(
                        name=item.get("name", ""),
                        address=item.get("address"),
                        location=GeoPoint(**loc) if loc else None,
                        rating=item.get("rating"),
                        image_url=item.get("image_url"),
                        ticket_price=item.get("ticket_price"),
                        tags=[],
                        source=item.get("source", dr.response.source or "演示数据"),
                    ))
                return out
        return []

    def _parse_hotels(self, results: list[DispatchResult]) -> list[Hotel]:
        for dr in results:
            if dr.task_type == "hotel" and dr.response.status == "success":
                items = dr.response.result.get("items") or []
                out = []
                for item in items[: self.settings.max_results]:
                    loc = item.get("location")
                    out.append(Hotel(
                        name=item.get("name", ""),
                        address=item.get("address"),
                        location=GeoPoint(**loc) if loc else None,
                        price_per_night=item.get("price_per_night"),
                        star=item.get("star"),
                        image_url=item.get("image_url"),
                        source=item.get("source", dr.response.source or "演示数据"),
                    ))
                return out
        return []

    def _parse_weather(self, results: list[DispatchResult]) -> list[DailyWeather]:
        for dr in results:
            if dr.task_type == "weather" and dr.response.status == "success":
                forecasts = dr.response.result.get("forecasts") or []
                out = []
                for f in forecasts:
                    try:
                        d = datetime.date.fromisoformat(f["date"])
                    except (ValueError, KeyError):
                        continue
                    out.append(DailyWeather(
                        date=d,
                        day_desc=f.get("day_desc"),
                        temp_min=f.get("temp_min"),
                        temp_max=f.get("temp_max"),
                        precipitation=f.get("precipitation"),
                        wind=f.get("wind"),
                        source=f.get("source", dr.response.source or "演示数据"),
                    ))
                return out
        return []

    async def _fetch_image(self, query: str) -> str | None:
        try:
            result = await self.mcp.call("unsplash_search", {"query": query, "per_page": 1})
            if result.status == "success":
                images = result.content.get("images") or []
                if images:
                    return images[0].get("url")
        except Exception:
            pass
        return None

    async def subscribe_events(self, task_id: str) -> AsyncGenerator[str, None]:
        queue = self._events.get(task_id)
        if queue is None:
            if task_id in self._results:
                yield f"event: completed\ndata: 行程规划完成\n\n"
            else:
                yield f"event: failed\ndata: 任务不存在\n\n"
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
                yield event
                if "completed" in event or "failed" in event:
                    break
            except asyncio.TimeoutError:
                yield f"event: heartbeat\ndata: keepalive\n\n"

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        return self._results.get(task_id)

    async def health(self) -> DependencyHealth:
        try:
            tools = self.mcp.definitions()
        except Exception:
            tools = []
        available = len(tools) > 0
        detail = "tools=" + ",".join(t.name for t in tools) if available else "no tools registered"
        return DependencyHealth(
            name="orchestrator",
            available=available,
            detail=detail,
        )


def build_mcp_connection(settings: Settings, registry):
    if settings.mcp_transport == "streamable-http":
        return StreamableHttpMCPConnection(settings.amap_mcp_url)
    return InProcessMCPConnection(registry)


def build_orchestrator_service(settings: Settings | None = None) -> OrchestratorService:
    from app.a2a.agent import create_attraction_agent, create_hotel_agent, create_weather_agent
    from app.a2a.client import build_a2a_client
    from app.orchestrator.planner import build_planner_agent

    settings = settings or Settings()
    registry = build_default_registry(settings)
    mcp = build_mcp_connection(settings, registry)
    client = build_a2a_client(settings)

    if settings.a2a_transport == "in-process":
        conn = client.in_process
        if conn is not None:
            conn.register("attraction", create_attraction_agent(settings, mcp).handle)
            conn.register("weather", create_weather_agent(settings, mcp).handle)
            conn.register("hotel", create_hotel_agent(settings, mcp).handle)

    agent = OrchestratorAgent(client)
    planner = build_planner_agent(settings)
    store = SessionStore()
    return OrchestratorService(client, agent, planner, store, mcp, settings)
