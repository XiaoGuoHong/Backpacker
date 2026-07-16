from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import Settings, get_settings


_UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"


class UnsplashClient:
    """Unsplash 图片搜索客户端（简单封装，无 Key 时返回占位图）。"""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.access_key = self.settings.unsplash_access_key

    @property
    def available(self) -> bool:
        return bool(self.access_key)

    async def search(self, query: str, per_page: int = 5) -> dict[str, Any]:
        if not self.available:
            return {"images": [], "is_demo": True, "source": "演示数据"}

        params = {"query": query, "per_page": per_page, "orientation": "landscape"}
        headers = {"Authorization": f"Client-ID {self.access_key}"}
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(_UNSPLASH_SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        images = []
        for result in data.get("results") or []:
            urls = result.get("urls") or {}
            small = urls.get("small") or urls.get("regular") or urls.get("raw")
            if small:
                images.append({
                    "url": small,
                    "alt": result.get("alt_description") or query,
                    "source": "Unsplash",
                    "author": (result.get("user") or {}).get("name", ""),
                })

        # 搜不到真实图：返回空列表，让前端用首字符占位（比外部占位图更可靠）
        if not images:
            return {"images": [], "is_demo": True, "source": "演示数据"}

        return {"images": images, "is_demo": False, "source": "Unsplash"}


def _placeholder_images(query: str) -> list[dict[str, Any]]:
    return [
        {
            "url": f"https://placehold.co/400x250?text={query}",
            "alt": f"{query} 占位图",
            "source": "演示数据",
            "author": "",
        }
    ]


async def unsplash_search(params: dict[str, Any]) -> dict[str, Any]:
    client = UnsplashClient()
    query = params.get("query", "")
    per_page = params.get("per_page", 5)
    if not isinstance(per_page, int):
        try:
            per_page = int(per_page)
        except (ValueError, TypeError):
            per_page = 5
    result = await client.search(query, per_page=per_page)
    return result
