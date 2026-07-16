from app.mcp.sources.unsplash import unsplash_search as _unsplash_search
from app.mcp.tool import ToolDefinition


def unsplash_search_definition() -> ToolDefinition:
    return ToolDefinition(
        name="unsplash_search",
        description="根据关键词搜索图片（景点配图），无 Key 时返回占位图",
        input_schema={"query": "string", "per_page": "integer(可选)"},
        output_schema={
            "images": "list[{url, alt, source, author}]",
            "is_demo": "boolean",
            "source": "string",
        },
        timeout_ms=8000,
        error_types=["E_TOOL_TIMEOUT", "E_TOOL_UNAVAILABLE"],
    )


async def unsplash_search_handler(params: dict) -> dict:
    return await _unsplash_search(params)
