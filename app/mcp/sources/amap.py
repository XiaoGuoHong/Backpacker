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


_DEMO_ATTRACTIONS_BY_CITY: dict[str, list[dict[str, Any]]] = {
    "北京": [
        {"name": "故宫博物院", "address": "北京市东城区景山前街4号", "location": {"lng": 116.4039, "lat": 39.9165}, "rating": 4.9, "ticket_price": 60},
        {"name": "颐和园", "address": "北京市海淀区新建宫门路19号", "location": {"lng": 116.2756, "lat": 39.9999}, "rating": 4.8, "ticket_price": 30},
        {"name": "天坛公园", "address": "北京市东城区天坛内里甲1号", "location": {"lng": 116.4100, "lat": 39.8822}, "rating": 4.7, "ticket_price": 15},
        {"name": "八达岭长城", "address": "北京市延庆区八达岭特区内", "location": {"lng": 116.0245, "lat": 40.3598}, "rating": 4.8, "ticket_price": 40},
        {"name": "鸟巢（国家体育场）", "address": "北京市朝阳区国家体育场南路1号", "location": {"lng": 116.3974, "lat": 39.9929}, "rating": 4.6, "ticket_price": 50},
        {"name": "南锣鼓巷", "address": "北京市东城区南锣鼓巷", "location": {"lng": 116.4040, "lat": 39.9362}, "rating": 4.4, "ticket_price": 0},
        {"name": "798艺术区", "address": "北京市朝阳区酒仙桥路4号", "location": {"lng": 116.4968, "lat": 39.9842}, "rating": 4.5, "ticket_price": 0},
        {"name": "北海公园", "address": "北京市西城区文津街1号", "location": {"lng": 116.3956, "lat": 39.9259}, "rating": 4.6, "ticket_price": 10},
        {"name": "恭王府", "address": "北京市西城区前海西街17号", "location": {"lng": 116.3893, "lat": 39.9406}, "rating": 4.6, "ticket_price": 40},
    ],
    "上海": [
        {"name": "外滩", "address": "上海市黄浦区中山东一路", "location": {"lng": 121.4903, "lat": 31.2417}, "rating": 4.8, "ticket_price": 0},
        {"name": "东方明珠广播电视塔", "address": "上海市浦东新区世纪大道1号", "location": {"lng": 121.4985, "lat": 31.2397}, "rating": 4.7, "ticket_price": 120},
        {"name": "上海迪士尼乐园", "address": "上海市浦东新区川沙镇", "location": {"lng": 121.6737, "lat": 31.1453}, "rating": 4.8, "ticket_price": 475},
        {"name": "豫园", "address": "上海市黄安区安仁街218号", "location": {"lng": 121.4909, "lat": 31.2273}, "rating": 4.6, "ticket_price": 40},
        {"name": "南京路步行街", "address": "上海市黄浦区南京东路", "location": {"lng": 121.4788, "lat": 31.2361}, "rating": 4.5, "ticket_price": 0},
        {"name": "田子坊", "address": "上海市黄浦区泰康路274-278弄", "location": {"lng": 121.4668, "lat": 31.2120}, "rating": 4.4, "ticket_price": 0},
        {"name": "上海博物馆", "address": "上海市黄浦区人民大道201号", "location": {"lng": 121.4766, "lat": 31.2303}, "rating": 4.7, "ticket_price": 0},
        {"name": "城隍庙", "address": "上海市黄浦区方浜中路249号", "location": {"lng": 121.4925, "lat": 31.2273}, "rating": 4.5, "ticket_price": 10},
        {"name": "静安寺", "address": "上海市静安区南京西路1686号", "location": {"lng": 121.4456, "lat": 31.2229}, "rating": 4.5, "ticket_price": 30},
    ],
    "杭州": [
        {"name": "西湖", "address": "杭州市西湖区龙井路1号", "location": {"lng": 120.1487, "lat": 30.2426}, "rating": 4.9, "ticket_price": 0},
        {"name": "灵隐寺", "address": "杭州市西湖区灵隐路法云弄1号", "location": {"lng": 120.0990, "lat": 30.2417}, "rating": 4.6, "ticket_price": 45},
        {"name": "西溪湿地", "address": "杭州市西湖区天目山路518号", "location": {"lng": 120.0792, "lat": 30.2690}, "rating": 4.6, "ticket_price": 80},
        {"name": "千岛湖", "address": "杭州市淳安县千岛湖镇", "location": {"lng": 119.0143, "lat": 29.6097}, "rating": 4.7, "ticket_price": 130},
        {"name": "宋城", "address": "杭州市西湖区之江路148号", "location": {"lng": 120.1010, "lat": 30.1967}, "rating": 4.5, "ticket_price": 300},
        {"name": "河坊街", "address": "杭州市上城区河坊街", "location": {"lng": 120.1690, "lat": 30.2460}, "rating": 4.4, "ticket_price": 0},
        {"name": "雷峰塔", "address": "杭州市西湖区南山路15号", "location": {"lng": 120.1500, "lat": 30.2309}, "rating": 4.5, "ticket_price": 40},
    ],
    "成都": [
        {"name": "宽窄巷子", "address": "成都市青羊区宽窄巷子", "location": {"lng": 104.0610, "lat": 30.6738}, "rating": 4.6, "ticket_price": 0},
        {"name": "都江堰", "address": "成都市都江堰市公园路", "location": {"lng": 103.6103, "lat": 30.9885}, "rating": 4.7, "ticket_price": 80},
        {"name": "大熊猫繁育研究基地", "address": "成都市成华区熊猫大道1375号", "location": {"lng": 104.1470, "lat": 30.7320}, "rating": 4.8, "ticket_price": 55},
        {"name": "武侯祠", "address": "成都市武侯区武侯祠大街231号", "location": {"lng": 104.0437, "lat": 30.6420}, "rating": 4.5, "ticket_price": 50},
        {"name": "锦里", "address": "成都市武侯区武侯祠大街231号", "location": {"lng": 104.0439, "lat": 30.6419}, "rating": 4.4, "ticket_price": 0},
        {"name": "青城山", "address": "成都市都江堰市青城山", "location": {"lng": 103.5633, "lat": 30.9020}, "rating": 4.7, "ticket_price": 80},
        {"name": "春熙路", "address": "成都市锦江区春熙路", "location": {"lng": 104.0832, "lat": 30.6593}, "rating": 4.5, "ticket_price": 0},
    ],
    "西安": [
        {"name": "兵马俑", "address": "西安市临潼区秦始皇帝陵博物院", "location": {"lng": 109.2784, "lat": 34.3848}, "rating": 4.9, "ticket_price": 120},
        {"name": "大雁塔", "address": "西安市雁塔区雁塔南路", "location": {"lng": 108.9647, "lat": 34.2186}, "rating": 4.7, "ticket_price": 30},
        {"name": "西安城墙", "address": "西安市碑林区南大街", "location": {"lng": 108.9400, "lat": 34.2567}, "rating": 4.7, "ticket_price": 54},
        {"name": "回民街", "address": "西安市莲湖区回民街", "location": {"lng": 108.9400, "lat": 34.2655}, "rating": 4.4, "ticket_price": 0},
        {"name": "华清宫", "address": "西安市临潼区华清路38号", "location": {"lng": 109.2137, "lat": 34.3660}, "rating": 4.5, "ticket_price": 120},
        {"name": "陕西历史博物馆", "address": "西安市雁塔区小寨东路91号", "location": {"lng": 108.9538, "lat": 34.2267}, "rating": 4.8, "ticket_price": 30},
        {"name": "大唐不夜城", "address": "西安市雁塔区慈恩路", "location": {"lng": 108.9613, "lat": 34.2140}, "rating": 4.6, "ticket_price": 0},
    ],
}

_DEMO_HOTELS_BY_CITY: dict[str, list[dict[str, Any]]] = {
    "北京": [
        {"name": "北京王府井希尔顿酒店", "address": "北京市东城区王府井大街8号", "location": {"lng": 116.4117, "lat": 39.9143}, "price_per_night": 980, "star": 5},
        {"name": "北京三里屯通盈中心洲际酒店", "address": "北京市朝阳区三里屯工体北路", "location": {"lng": 116.4473, "lat": 39.9347}, "price_per_night": 1280, "star": 5},
        {"name": "北京前门建国饭店", "address": "北京市西城区前门东大街", "location": {"lng": 116.4026, "lat": 39.8995}, "price_per_night": 420, "star": 4},
    ],
    "上海": [
        {"name": "上海外滩茂悦大酒店", "address": "上海市黄浦 ltd中山东一路32号", "location": {"lng": 121.4929, "lat": 31.2460}, "price_per_night": 1180, "star": 5},
        {"name": "上海新天地朗廷酒店", "address": "上海市黄浦区马当路99号", "location": {"lng": 121.4709, "lat": 31.2125}, "price_per_night": 1380, "star": 5},
        {"name": "上海世茂皇家艾美酒店", "address": "上海市浦东新区世纪大道", "location": {"lng": 121.5038, "lat": 31.2317}, "price_per_night": 880, "star": 5},
    ],
    "杭州": [
        {"name": "杭州西湖四季酒店", "address": "杭州市西湖区灵隐路5号", "location": {"lng": 120.0994, "lat": 30.2497}, "price_per_night": 1680, "star": 5},
        {"name": "杭州君悦酒店", "address": "杭州市拱墅区湖墅南路8号", "location": {"lng": 120.1570, "lat": 30.2700}, "price_per_night": 720, "star": 5},
        {"name": "西溪喜来登度假酒店", "address": "杭州市西湖区西溪天堂", "location": {"lng": 120.0793, "lat": 30.2697}, "price_per_night": 580, "star": 4},
    ],
    "成都": [
        {"name": "成都太古里博舍酒店", "address": "成都市锦江区笔帖式街81号", "location": {"lng": 104.0843, "lat": 30.6563}, "price_per_night": 1480, "star": 5},
        {"name": "成都香格里拉大酒店", "address": "成都市锦江区滨江东路9号", "location": {"lng": 104.0833, "lat": 30.6497}, "price_per_night": 880, "star": 5},
        {"name": "成都瑞吉酒店", "address": "成都市青羊区顺城大街269号", "location": {"lng": 104.0732, "lat": 30.6688}, "price_per_night": 650, "star": 5},
    ],
    "西安": [
        {"name": "西安钟楼希尔顿酒店", "address": "西安市碑林区东大街110号", "location": {"lng": 108.9474, "lat": 34.2613}, "price_per_night": 720, "star": 5},
        {"name": "西安大唐西市索菲特酒店", "address": "西安市莲湖区劳动南路14号", "location": {"lng": 108.9220, "lat": 34.2636}, "price_per_night": 580, "star": 5},
        {"name": "西安大雁塔假日酒店", "address": "西安市雁塔区南二环西段6号", "location": {"lng": 108.9530, "lat": 34.2307}, "price_per_night": 480, "star": 4},
    ],
}


def _demo_pois(city: str, keyword: str) -> list[dict[str, Any]]:
    """返回该城市的 demo 景点（真实存在的著名景点，带坐标便于地图展示）。"""
    key = city.strip()
    pool: list[dict[str, Any]] = list(_DEMO_ATTRACTIONS_BY_CITY.get(key, []))
    # 没有该城市，回退到通用（占位但保证可用）
    if not pool:
        pool = [
            {"name": f"{key}中心地标", "address": f"{key}市中心", "location": None, "rating": 4.5, "ticket_price": None},
            {"name": f"{key}历史街区", "address": f"{key}老城区", "location": None, "rating": 4.4, "ticket_price": None},
            {"name": f"{key}美食街", "address": f"{key}商业街", "location": None, "rating": 4.3, "ticket_price": None},
        ]
    # 标 source，并按关键词粗筛
    is_hotel = "酒店" in (keyword or "")
    out: list[dict[str, Any]] = []
    if is_hotel:
        for h in _DEMO_HOTELS_BY_CITY.get(key, []):
            item = {**h, "typecode": "100000", "source": "演示数据"}
            out.append(item)
        if not out:
            out = [{"name": f"{key}推荐酒店", "address": f"{key}市中心", "location": None, "price_per_night": None, "star": 4, "typecode": "100000", "source": "演示数据"}]
    else:
        for a in pool:
            item = {**a, "typecode": "110000", "source": "演示数据"}
            out.append(item)
    return out


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
