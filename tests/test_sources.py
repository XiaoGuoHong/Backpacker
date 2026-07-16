import anyio
import httpx

from app.core.config import Settings
from app.mcp.connection import InProcessMCPConnection
from app.mcp.registry import build_default_registry
from app.mcp.tools.weather import make_weather_handler


def test_weather_demo_handler_marks_demo():
    out = anyio.run(make_weather_handler, {"city": "北京", "start_date": "2025-08-11", "days": 1})
    assert out["is_demo"] is True
    assert out["source"] == "演示数据"


def test_weather_real_handler_maps_open_meteo(monkeypatch):
    import app.mcp.sources.weather_open_meteo as wm

    async def fake_get_json(url, params):
        if "geocoding" in url:
            return {"results": [{"name": "北京", "latitude": 39.9, "longitude": 116.4}]}
        return {
            "daily": {
                "time": ["2025-08-11"],
                "weather_code": [1],
                "temperature_2m_min": [22.0],
                "temperature_2m_max": [30.0],
                "precipitation_probability_max": [10],
                "wind_speed_10m_max": [12.0],
            }
        }

    monkeypatch.setattr(wm, "_get_json", fake_get_json)
    out = anyio.run(make_weather_handler, {"city": "北京", "start_date": "2025-08-11", "days": 1, "weather_source": "open-meteo"})
    assert out["is_demo"] is False
    assert out["source"] == "Open-Meteo"
    assert out["city"] == "北京"
    assert len(out["forecasts"]) == 1


def test_weather_real_handler_city_not_found(monkeypatch):
    import app.mcp.sources.weather_open_meteo as wm

    async def fake_get_json(url, params):
        return {"results": []}

    monkeypatch.setattr(wm, "_get_json", fake_get_json)
    out = anyio.run(make_weather_handler, {"city": "不存在城", "start_date": "2025-08-11", "days": 1, "weather_source": "open-meteo"})
    assert out["is_demo"] is True  # 失败后回退到 demo


def test_weather_source_mode_picks_real(monkeypatch):
    monkeypatch.setenv("WEATHER_SOURCE", "open-meteo")
    settings = Settings(environment="test", mcp_transport="in-process")
    conn = InProcessMCPConnection(build_default_registry(settings))
    assert conn.definition("weather_tool") is not None


# ── QWeather 测试 ────────────────────────────────────────────

def test_weather_qweather_handler_marks_not_demo(monkeypatch):
    monkeypatch.setenv("WEATHER_API_KEY", "fake_key")
    import app.mcp.sources.weather_qweather as wq

    async def fake_get_json(url, params, api_key):
        return {
            "code": "200",
            "daily": [
                {
                    "fxDate": "2025-08-11",
                    "tempMax": "35",
                    "tempMin": "24",
                    "textDay": "晴",
                    "precip": "0",
                    "windDirDay": "北风",
                    "windScaleDay": "3-4",
                }
            ],
        }

    monkeypatch.setattr(wq, "_get_json", fake_get_json)
    out = anyio.run(make_weather_handler, {"city": "北京", "start_date": "2025-08-11", "days": 1, "weather_source": "qweather"})
    assert out["is_demo"] is False
    assert out["source"] == "QWeather"
    assert len(out["forecasts"]) == 1
    assert out["forecasts"][0]["day_desc"] == "晴"


def test_weather_qweather_missing_api_key(monkeypatch):
    monkeypatch.delenv("WEATHER_API_KEY", raising=False)
    import app.mcp.sources.weather_qweather as wq

    out = anyio.run(wq.weather_qweather, {"city": "北京", "date": "2025-08-11"})
    assert out["is_demo"] is False
    assert out["error"] == "missing_api_key"


def test_amap_client_no_key_returns_demo():
    from app.mcp.sources.amap import AmapClient
    import asyncio

    client = AmapClient(Settings(environment="test"))
    assert not client.available
    out = asyncio.run(client.text_search("景点", "北京"))
    assert out["status"] == "0"


def test_unsplash_client_no_key_returns_placeholder():
    from app.mcp.sources.unsplash import UnsplashClient
    import asyncio

    client = UnsplashClient(Settings(environment="test"))
    assert not client.available
    out = asyncio.run(client.search("故宫"))
    assert out["is_demo"] is True
    assert len(out["images"]) == 1
