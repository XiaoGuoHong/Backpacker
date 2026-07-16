import anyio

from app.core.config import Settings
from app.mcp.connection import InProcessMCPConnection
from app.mcp.registry import build_default_registry


def test_mcp_call_weather_tool():
    async def run():
        conn = InProcessMCPConnection(
            build_default_registry(Settings(environment="test", mcp_transport="in-process"))
        )
        res = await conn.call("weather_tool", {"city": "北京", "start_date": "2025-08-11", "days": 1})
        assert res.status == "success"
        assert res.content["city"] == "北京"
        assert res.content["is_demo"] is True

    anyio.run(run)


def test_mcp_call_amap_poi_search():
    async def run():
        conn = InProcessMCPConnection(
            build_default_registry(Settings(environment="test", mcp_transport="in-process"))
        )
        res = await conn.call("amap_poi_search", {"keywords": "景点", "city": "北京"})
        assert res.status == "success"
        assert "items" in res.content
        assert res.content["is_demo"] is True

    anyio.run(run)


def test_mcp_unknown_tool_failed():
    async def run():
        conn = InProcessMCPConnection(
            build_default_registry(Settings(environment="test", mcp_transport="in-process"))
        )
        res = await conn.call("ghost_tool", {})
        assert res.status == "failed"
        assert res.error_code == "E_TOOL_UNAVAILABLE"

    anyio.run(run)


def test_mcp_definitions_registered():
    registry = build_default_registry(Settings(environment="test", mcp_transport="in-process"))
    names = {d.name for d in registry.list()}
    assert {"weather_tool", "amap_poi_search", "unsplash_search"} <= names
