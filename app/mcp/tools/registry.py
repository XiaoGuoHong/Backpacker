from app.core.config import Settings, get_settings
from app.mcp.sql.db_tool import make_db_query_tool
from app.mcp.tool import MCPRegistry, ToolDefinition
from app.mcp.tools import amap_poi_search, unsplash_search, weather


def _db_tool_definition() -> ToolDefinition:
    return ToolDefinition(
        name="db_query_tool",
        description="只读数据库查询（受白名单与单条只读限制）",
        input_schema={"sql": "string"},
        output_schema={"columns": "array", "rows": "array", "truncated": "bool"},
        timeout_ms=3000,
        error_types=["E_SQL_REJECTED", "E_TOOL_UNAVAILABLE"],
    )


def register_all(registry: MCPRegistry, settings: Settings) -> None:
    registry.register(
        weather.weather_tool_definition(),
        lambda p: weather.make_weather_handler({**p, "weather_source": settings.weather_source}),
    )
    registry.register(
        amap_poi_search.amap_poi_search_definition(),
        amap_poi_search.amap_poi_search_handler,
    )
    registry.register(
        unsplash_search.unsplash_search_definition(),
        unsplash_search.unsplash_search_handler,
    )
    if settings.db_enabled:
        registry.register(_db_tool_definition(), make_db_query_tool(settings))


def build_default_registry(settings: Settings | None = None) -> MCPRegistry:
    settings = settings or get_settings()
    registry = MCPRegistry()
    register_all(registry, settings)
    return registry
