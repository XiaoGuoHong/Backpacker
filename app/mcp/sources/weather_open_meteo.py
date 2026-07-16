import httpx
from datetime import datetime, timezone

_WMO_TEXT = {
    0: "晴",
    1: "晴间多云",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "大毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "阵雨",
    81: "强阵雨",
    82: "暴雨",
    95: "雷阵雨",
    96: "雷阵雨伴冰雹",
    99: "强雷暴伴冰雹",
}

_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FC_URL = "https://api.open-meteo.com/v1/forecast"


async def _get_json(url: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _weather_text(code: int) -> str:
    return _WMO_TEXT.get(int(code), "未知")


async def weather_open_meteo(params: dict) -> dict:
    city = params.get("city")
    date = params.get("date")
    if not city or not date:
        return {"city": city, "date": date, "source": "Open-Meteo", "is_demo": False,
                "error": "missing city or date"}

    geo = await _get_json(_GEO_URL, {"name": city, "count": 1, "language": "zh"})
    results = geo.get("results") or []
    if not results:
        return {"city": city, "date": date, "source": "Open-Meteo", "is_demo": False,
                "error": "city_not_found"}

    loc = results[0]
    lat, lon = loc["latitude"], loc["longitude"]

    try:
        fc = await _get_json(
            _FC_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,wind_speed_10m_max",
                "timezone": "Asia/Shanghai",
                "start_date": date,
                "end_date": date,
            },
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            return {
                "city": loc.get("name", city),
                "date": date,
                "error": "date_out_of_range",
                "source": "Open-Meteo",
                "source_updated_at": datetime.now(timezone.utc).isoformat(),
                "is_demo": False,
            }
        raise

    daily = fc.get("daily", {})
    times = daily.get("time", [])
    idx = times.index(date) if date in times else 0

    return {
        "city": loc.get("name", city),
        "date": date,
        "condition": _weather_text(daily.get("weather_code", [0])[idx]),
        "temperature": {
            "low": daily.get("temperature_2m_min", [0])[idx],
            "high": daily.get("temperature_2m_max", [0])[idx],
        },
        "precipitation": daily.get("precipitation_probability_max", [0])[idx],
        "wind": f"{daily.get('wind_speed_10m_max', [0])[idx]} km/h",
        "source": "Open-Meteo",
        "source_updated_at": datetime.now(timezone.utc).isoformat(),
        "is_demo": False,
    }
