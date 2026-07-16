from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.mcp.sources.amap import amap_weather
from app.mcp.sources.weather_open_meteo import weather_open_meteo
from app.mcp.sources.weather_qweather import weather_qweather
from app.mcp.tool import ToolDefinition


def weather_demo_for_days(params: dict) -> dict[str, Any]:
    city = params.get("city", "未知城市")
    start = params.get("start_date", date.today().isoformat())
    days = int(params.get("days", 3))
    if isinstance(start, date):
        start = start.isoformat()
    forecasts = []
    for i in range(days):
        d = date.fromisoformat(start) + timedelta(days=i)
        forecasts.append({
            "date": d.isoformat(),
            "day_desc": "晴",
            "temp_min": 22.0,
            "temp_max": 30.0,
            "precipitation": 10.0,
            "wind": "东北风 3级",
            "source": "演示数据",
        })
    return {
        "city": city,
        "forecasts": forecasts,
        "source": "演示数据",
        "source_updated_at": datetime.now(timezone.utc).isoformat(),
        "is_demo": True,
    }


def weather_tool_definition() -> ToolDefinition:
    return ToolDefinition(
        name="weather_tool",
        description="查询指定城市未来若干天的天气预报",
        input_schema={
            "city": "string",
            "start_date": "string(YYYY-MM-DD)",
            "days": "integer(1-30)",
        },
        output_schema={
            "city": "string",
            "forecasts": "list[{date, day_desc, temp_min, temp_max, precipitation, wind, source}]",
        },
        timeout_ms=10000,
        error_types=["E_TOOL_TIMEOUT", "E_TOOL_UNAVAILABLE", "E_NO_RESULT"],
    )


async def _open_meteo_forecasts(city: str, start: str, days: int) -> list[dict[str, Any]]:
    forecasts = []
    for i in range(days):
        d = date.fromisoformat(start) + timedelta(days=i)
        result = await weather_open_meteo({"city": city, "date": d.isoformat()})
        if "error" in result:
            continue
        forecasts.append({
            "date": result["date"],
            "day_desc": result["condition"],
            "temp_min": result.get("temperature", {}).get("low"),
            "temp_max": result.get("temperature", {}).get("high"),
            "precipitation": result.get("precipitation"),
            "wind": result.get("wind"),
            "source": result.get("source", "Open-Meteo"),
        })
    return forecasts


async def _qweather_forecasts(city: str, start: str, days: int) -> list[dict[str, Any]]:
    forecasts = []
    for i in range(days):
        d = date.fromisoformat(start) + timedelta(days=i)
        result = await weather_qweather({"city": city, "date": d.isoformat()})
        if "error" in result:
            continue
        forecasts.append({
            "date": result["date"],
            "day_desc": result["condition"],
            "temp_min": result.get("temperature", {}).get("low"),
            "temp_max": result.get("temperature", {}).get("high"),
            "precipitation": result.get("precipitation"),
            "wind": result.get("wind"),
            "source": result.get("source", "QWeather"),
        })
    return forecasts


async def make_weather_handler(params: dict[str, Any]) -> dict[str, Any]:
    city = params.get("city", "")
    start = params.get("start_date", date.today().isoformat())
    days = int(params.get("days", 3))
    if isinstance(start, date):
        start = start.isoformat()

    # Try Amap weather first
    amap_result = await amap_weather({"city": city})
    forecasts = amap_result.get("forecasts") or []
    if forecasts and not amap_result.get("is_demo"):
        return {
            "city": city,
            "forecasts": [f for f in forecasts if f["date"] >= start][:days],
            "source": "高德天气",
            "source_updated_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
        }

    mode = params.get("weather_source", "open-meteo")
    if mode == "demo":
        return weather_demo_for_days({"city": city, "start_date": start, "days": days})
    if mode == "qweather":
        forecasts = await _qweather_forecasts(city, start, days)
    elif mode == "amap":
        amap_demo = await amap_weather({"city": city})
        forecasts = (amap_demo.get("forecasts") or [])
        forecasts = [f for f in forecasts if f.get("date", "") >= start][:days]
    else:
        forecasts = await _open_meteo_forecasts(city, start, days)

    if forecasts:
        return {
            "city": city,
            "forecasts": forecasts,
            "source": "Open-Meteo" if mode == "open-meteo" else "QWeather",
            "source_updated_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
        }

    return weather_demo_for_days({"city": city, "start_date": start, "days": days})
