import asyncio
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import Settings, get_settings


_AMAP_GEO_URL = "https://restapi.amap.com/v3/geocode/geo"
_AMAP_POI_URL = "https://restapi.amap.com/v3/place/text"
_AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
_AMAP_DIRECTION_URL = "https://restapi.amap.com/v3/direction/{}"


class AmapClient:
    """高德 Web 服务客户端（单例），内置缓存与限速。"""

    _instance: "AmapClient | None" = None
    _lock: asyncio.Lock | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._lock = asyncio.Lock()
        return cls._instance

    def __init__(self, settings: Settings | None = None):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.settings = settings or get_settings()
        self.key = self.settings.amap_api_key
        self.cache_ttl = self.settings.amap_cache_ttl
        self.rate_limit = self.settings.amap_rate_limit
        self._cache: dict[str, tuple[Any, float]] = {}
        self._last_call: float = 0.0
        self._initialized = True

    @property
    def available(self) -> bool:
        return bool(self.key)

    async def _rate_limited_get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.rate_limit > 0:
            min_interval = 1.0 / self.rate_limit
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_call
                if elapsed < min_interval:
                    await asyncio.sleep(min_interval - elapsed)
                self._last_call = time.monotonic()

        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    def _cache_key(self, url: str, params: dict[str, Any]) -> str:
        items = sorted((k, str(v)) for k, v in params.items() if v is not None)
        query = "&".join(f"{k}={v}" for k, v in items)
        return f"{url}?{query}"

    async def _cached_call(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        key = self._cache_key(url, params)
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and now - cached[1] < self.cache_ttl:
            return cached[0]
        data = await self._rate_limited_get(url, params)
        self._cache[key] = (data, now)
        return data

    async def geocode(self, address: str) -> dict[str, Any]:
        if not self.available:
            return {"status": "0", "info": "NO_KEY", "geocodes": []}
        params = {"key": self.key, "address": address, "output": "JSON"}
        return await self._cached_call(_AMAP_GEO_URL, params)

    async def text_search(self, keywords: str, city: str | None = None, type_code: str | None = None) -> dict[str, Any]:
        if not self.available:
            return {"status": "0", "info": "NO_KEY", "pois": []}
        params: dict[str, Any] = {
            "key": self.key,
            "keywords": keywords,
            "offset": 20,
            "page": 1,
            "output": "JSON",
        }
        if city:
            params["city"] = city
        if type_code:
            params["types"] = type_code
        return await self._cached_call(_AMAP_POI_URL, params)

    async def weather(self, city: str) -> dict[str, Any]:
        if not self.available:
            return {"status": "0", "info": "NO_KEY", "lives": [], "forecasts": []}
        params = {"key": self.key, "city": city, "extensions": "all", "output": "JSON"}
        return await self._cached_call(_AMAP_WEATHER_URL, params)

    async def direction(
        self,
        route_type: str,
        origin: str,
        destination: str,
    ) -> dict[str, Any]:
        if not self.available:
            return {"status": "0", "info": "NO_KEY", "route": {"paths": []}}
        url = _AMAP_DIRECTION_URL.format(route_type)
        params = {
            "key": self.key,
            "origin": origin,
            "destination": destination,
            "output": "JSON",
        }
        return await self._cached_call(url, params)


def _format_pois(data: dict[str, Any], source_tag: str) -> list[dict[str, Any]]:
    pois = data.get("pois") or []
    out = []
    for poi in pois:
        location = poi.get("location", "")
        lng, lat = None, None
        if location and "," in location:
            try:
                lng_s, lat_s = location.split(",", 1)
                lng, lat = float(lng_s), float(lat_s)
            except ValueError:
                pass
        out.append({
            "name": poi.get("name", ""),
            "address": poi.get("address", ""),
            "location": {"lng": lng, "lat": lat} if lng is not None else None,
            "rating": None,
            "typecode": poi.get("typecode", ""),
            "tel": poi.get("tel", ""),
            "business_area": poi.get("business_area", ""),
            "source": source_tag,
        })
    return out


def _format_weather(data: dict[str, Any], source_tag: str) -> list[dict[str, Any]]:
    forecasts = data.get("forecasts") or []
    out = []
    for item in forecasts:
        for cast in item.get("casts") or []:
            out.append({
                "date": cast.get("date"),
                "day_desc": f"{cast.get('dayweather', '')}/{cast.get('nightweather', '')}",
                "temp_min": _to_float(cast.get("nighttemp")),
                "temp_max": _to_float(cast.get("daytemp")),
                "precipitation": None,
                "wind": f"{cast.get('daywind', '')} {cast.get('daypower', '')}",
                "source": source_tag,
            })
    return out


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


async def amap_poi_search(params: dict[str, Any]) -> dict[str, Any]:
    client = AmapClient()
    keywords = params.get("keywords", "")
    city = params.get("city", "")
    type_code = params.get("type", "")
    if not client.available:
        return {"items": _demo_pois(city, keywords or type_code), "is_demo": True, "source": "演示数据"}
    data = await client.text_search(keywords=keywords, city=city, type_code=type_code)
    status = str(data.get("status", "0"))
    if status != "1":
        return {"items": _demo_pois(city, keywords or type_code), "is_demo": True, "source": "演示数据"}
    items = _format_pois(data, "高德地图")
    return {"items": items[:20], "is_demo": False, "source": "高德地图"}


async def amap_weather(params: dict[str, Any]) -> dict[str, Any]:
    client = AmapClient()
    city = params.get("city", "")
    if not client.available:
        return {"forecasts": _demo_weather(), "is_demo": True, "source": "演示数据"}
    data = await client.weather(city)
    status = str(data.get("status", "0"))
    if status != "1":
        return {"forecasts": _demo_weather(), "is_demo": True, "source": "演示数据"}
    forecasts = _format_weather(data, "高德天气")
    return {"forecasts": forecasts, "is_demo": False, "source": "高德天气"}


async def amap_direction(params: dict[str, Any]) -> dict[str, Any]:
    client = AmapClient()
    route_type = params.get("route_type", "driving")
    origin = params.get("origin", "")
    destination = params.get("destination", "")
    if not client.available:
        return {"paths": [], "is_demo": True, "source": "演示数据"}
    data = await client.direction(route_type, origin, destination)
    status = str(data.get("status", "0"))
    if status != "1":
        return {"paths": [], "is_demo": True, "source": "演示数据"}
    paths = (data.get("route") or {}).get("paths") or []
    return {"paths": paths, "is_demo": False, "source": "高德地图"}


def _demo_pois(city: str, keyword: str) -> list[dict[str, Any]]:
    return [
        {"name": f"{city}{keyword}示范点", "address": f"{city}市中心", "location": None, "rating": 4.5, "typecode": "", "source": "演示数据"},
        {"name": f"{city}必游之地", "address": f"{city}风景区", "location": None, "rating": 4.2, "typecode": "", "source": "演示数据"},
    ]


def _demo_weather() -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    days = []
    for i in range(5):
        d = today + timedelta(days=i)
        days.append({
            "date": d.isoformat(),
            "day_desc": "晴/多云",
            "temp_min": 20.0 + i,
            "temp_max": 28.0 + i,
            "precipitation": None,
            "wind": "东南风 3级",
            "source": "演示数据",
        })
    return days
