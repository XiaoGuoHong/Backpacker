import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from app.core.config import Settings
from app.mcp.sql.db_tool import make_db_query_tool
from app.mcp.tools import amap_poi_search, unsplash_search, weather


async def _call(handler, params: dict):
    result = handler(params)
    if hasattr(result, "__await__"):
        result = await result
    return result


def build_amap_mcp_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("AmapMCP")
    mcp.settings.streamable_http_path = settings.mcp_http_path or "/mcp"
    mcp.settings.stateless_http = True

    @mcp.tool()
    async def amap_poi_search_tool(keywords: str, city: str, type: Optional[str] = None) -> dict:
        return await _call(amap_poi_search.amap_poi_search_handler, {"keywords": keywords, "city": city, "type": type})

    @mcp.tool()
    async def weather_tool(city: str, start_date: str, days: int) -> dict:
        return await _call(
            lambda p: weather.make_weather_handler({**p, "weather_source": settings.weather_source}),
            {"city": city, "start_date": start_date, "days": days},
        )

    @mcp.tool()
    async def unsplash_search_tool(query: str, per_page: Optional[int] = 5) -> dict:
        return await _call(unsplash_search.unsplash_search_handler, {"query": query, "per_page": per_page})

    if settings.db_enabled:
        db_handler = make_db_query_tool(settings)

        @mcp.tool()
        async def db_query_tool(sql: str) -> dict:
            return await _call(db_handler, {"sql": sql})

    return mcp


def build_mcp_server_app(settings: Settings):
    return build_amap_mcp_server(settings).streamable_http_app()


# 兼容旧名称
build_mcp_server = build_amap_mcp_server
