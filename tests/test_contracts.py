"""契约测试：A2A 消息、MCP 工具定义与 handler 输入输出的显式契约。"""
import anyio
import pytest
from datetime import date

from app.a2a.messages import A2AError, A2ARequest, A2AResponse
from app.core.config import Settings
from app.core.models import (
    Attraction,
    BudgetBreakdown,
    DailyWeather,
    GeoPoint,
    Hotel,
    Itinerary,
    ItineraryDay,
    TripRequest,
)
from app.mcp.connection import InProcessMCPConnection
from app.mcp.registry import build_default_registry
from app.mcp.tool import MCPToolResult, ToolDefinition


# ── A2A 消息契约 ────────────────────────────────────────

class TestA2AContracts:
    def test_request_required_fields(self):
        req = A2ARequest(request_id="r1", task_id="t1", task_type="weather")
        assert req.request_id == "r1"
        assert req.version == "1.0"

    def test_request_rejects_missing_required(self):
        with pytest.raises(Exception):
            A2ARequest(task_id="t1", task_type="weather")

    def test_response_success_shape(self):
        resp = A2AResponse(task_id="t1", status="success", result={"city": "北京"})
        assert resp.status == "success"
        assert resp.result["city"] == "北京"

    def test_response_timeout_shape(self):
        resp = A2AResponse(task_id="t1", status="timeout")
        assert resp.status == "timeout"

    def test_response_failed_shape(self):
        resp = A2AResponse(
            task_id="t1", status="failed",
            error=A2AError(code="E_TOOL_UNAVAILABLE", message="工具不可用"),
        )
        assert resp.status == "failed"
        assert resp.error is not None
        assert resp.error.code == "E_TOOL_UNAVAILABLE"


# ── 数据模型契约 ─────────────────────────────────────────

class TestDataModelContracts:
    def test_trip_request_valid(self):
        req = TripRequest(
            destination="北京",
            start_date=date(2025, 8, 11),
            days=3,
            budget_level="mid",
            interests=["历史文化"],
            hotel_type="舒适型",
        )
        assert req.destination == "北京"
        assert req.computed_days == 3

    def test_trip_request_end_date(self):
        req = TripRequest(
            destination="北京",
            start_date=date(2025, 8, 11),
            end_date=date(2025, 8, 13),
            budget_level="mid",
            interests=["历史文化"],
            hotel_type="舒适型",
        )
        assert req.computed_days == 3

    def test_itinerary_serializable(self):
        day = ItineraryDay(
            date=date(2025, 8, 11),
            index=1,
            attractions=[Attraction(name="故宫")],
            hotel=Hotel(name="酒店"),
            weather=DailyWeather(date=date(2025, 8, 11), day_desc="晴"),
        )
        itinerary = Itinerary(
            days=[day],
            budget=BudgetBreakdown(total=1000.0),
        )
        data = itinerary.model_dump(mode="json")
        assert data["days"][0]["date"] == "2025-08-11"


# ── MCP 工具定义契约 ─────────────────────────────────────

class TestMCPToolDefinitions:
    def setup_method(self):
        self.registry = build_default_registry(
            Settings(environment="test", mcp_transport="in-process")
        )

    def test_all_tools_have_required_fields(self):
        for tool in self.registry.list():
            assert tool.name, f"{tool.name} 缺少 name"
            assert isinstance(tool.input_schema, dict)
            assert tool.timeout_ms > 0, f"{tool.name} timeout 应 > 0"

    def test_tool_names_unique(self):
        names = [t.name for t in self.registry.list()]
        assert len(names) == len(set(names)), f"工具名重复: {names}"

    def test_weather_tool_schema(self):
        tool = self.registry.get("weather_tool")
        assert tool is not None
        assert "city" in tool.input_schema
        assert "start_date" in tool.input_schema
        assert "days" in tool.input_schema

    def test_amap_poi_search_tool_schema(self):
        tool = self.registry.get("amap_poi_search")
        assert tool is not None
        assert "keywords" in tool.input_schema
        assert "city" in tool.input_schema

    def test_unsplash_search_tool_schema(self):
        tool = self.registry.get("unsplash_search")
        assert tool is not None
        assert "query" in tool.input_schema

    def test_all_tools_have_error_types(self):
        for tool in self.registry.list():
            assert len(tool.error_types) > 0, f"{tool.name} 缺少 error_types"


# ── MCP Handler 输出契约 ─────────────────────────────────

class TestMCPHandlerContracts:
    def setup_method(self):
        registry = build_default_registry(
            Settings(environment="test", mcp_transport="in-process")
        )
        self.conn = InProcessMCPConnection(registry)

    def _call(self, name, params):
        return anyio.run(self.conn.call, name, params)

    def test_weather_handler_output_fields(self):
        res = self._call("weather_tool", {"city": "北京", "start_date": "2025-08-11", "days": 2})
        assert res.status == "success"
        c = res.content
        assert "city" in c
        assert "forecasts" in c
        assert isinstance(c["forecasts"], list)
        assert "is_demo" in c

    def test_amap_poi_search_handler_output_fields(self):
        res = self._call("amap_poi_search", {"keywords": "景点", "city": "北京"})
        assert res.status == "success"
        c = res.content
        assert "items" in c
        assert "is_demo" in c
        assert isinstance(c["items"], list)

    def test_unsplash_search_handler_output_fields(self):
        res = self._call("unsplash_search", {"query": "故宫"})
        assert res.status == "success"
        c = res.content
        assert "images" in c
        assert "is_demo" in c

    def test_unknown_tool_returns_failed(self):
        res = self._call("nonexistent_tool", {})
        assert res.status == "failed"
        assert res.error_code == "E_TOOL_UNAVAILABLE"


# ── MCPToolResult 契约 ───────────────────────────────────

class TestMCPToolResultContracts:
    def test_success_result_has_fetched_at(self):
        result = MCPToolResult(status="success", content={"test": 1})
        assert result.fetched_at is None

    def test_failed_result_has_error_code(self):
        result = MCPToolResult(status="failed", error_code="E_TOOL_UNAVAILABLE")
        assert result.error_code == "E_TOOL_UNAVAILABLE"
        assert result.content == {}


# ── 工具全套输出一致性契约 ───────────────────────────────

class TestAllToolsConsistency:
    @pytest.mark.parametrize("tool_name,params", [
        ("weather_tool", {"city": "北京", "start_date": "2025-08-11", "days": 2}),
        ("amap_poi_search", {"keywords": "景点", "city": "北京"}),
        ("unsplash_search", {"query": "故宫"}),
    ])
    def test_tool_returns_success(self, tool_name, params):
        registry = build_default_registry(
            Settings(environment="test", mcp_transport="in-process")
        )
        conn = InProcessMCPConnection(registry)
        res = anyio.run(conn.call, tool_name, params)
        assert res.status == "success", f"{tool_name} 应返回 success"
        assert isinstance(res.content, dict)
        assert len(res.content) > 0, f"{tool_name} 返回空结果"
