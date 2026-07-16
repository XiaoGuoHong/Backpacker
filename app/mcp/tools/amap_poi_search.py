from app.mcp.sources.amap import amap_poi_search as _amap_poi_search
from app.mcp.tool import ToolDefinition


def amap_poi_search_definition() -> ToolDefinition:
    return ToolDefinition(
        name="amap_poi_search",
        description="根据关键词和城市搜索高德 POI（景点、酒店等）",
        input_schema={
            "keywords": "string",
            "city": "string",
            "type": "string(可选，如 110000 景点、100000 酒店)",
        },
        output_schema={
            "items": "list[{name, address, location, rating, typecode, source}]",
            "is_demo": "boolean",
            "source": "string",
        },
        timeout_ms=10000,
        error_types=["E_TOOL_TIMEOUT", "E_TOOL_UNAVAILABLE", "E_NO_RESULT"],
    )


async def amap_poi_search_handler(params: dict) -> dict:
    return await _amap_poi_search(params)
