"""和风天气 QWeather 数据源适配器。

认证方式：X-QW-Api-Key Header
API Host 通过 QWEATHER_API_HOST 环境变量配置。
城市名→经纬度通过内置表映射，以坐标查询天气。
"""

import os
from datetime import datetime, timezone

import httpx

_DEFAULT_HOST = "https://devapi.qweather.com"

# 主要城市经纬度对照表（中文名 → (经度, 纬度)）
_CITY_COORDS: dict[str, tuple[float, float]] = {
    # 直辖市
    "北京": (116.41, 39.90), "北京市": (116.41, 39.90),
    "上海": (121.47, 31.23), "上海市": (121.47, 31.23),
    "天津": (117.20, 39.13), "天津市": (117.20, 39.13),
    "重庆": (106.55, 29.57), "重庆市": (106.55, 29.57),
    # 省会
    "广州": (113.26, 23.13), "广州市": (113.26, 23.13),
    "深圳": (114.06, 22.54), "深圳市": (114.06, 22.54),
    "成都": (104.07, 30.57), "成都市": (104.07, 30.57),
    "杭州": (120.15, 30.28), "杭州市": (120.15, 30.28),
    "武汉": (114.30, 30.60), "武汉市": (114.30, 30.60),
    "西安": (108.94, 34.26), "西安市": (108.94, 34.26),
    "南京": (118.80, 32.06), "南京市": (118.80, 32.06),
    "郑州": (113.62, 34.75), "郑州市": (113.62, 34.75),
    "长沙": (112.94, 28.23), "长沙市": (112.94, 28.23),
    "沈阳": (123.43, 41.80), "沈阳市": (123.43, 41.80),
    "济南": (117.12, 36.65), "济南市": (117.12, 36.65),
    "哈尔滨": (126.53, 45.80), "哈尔滨市": (126.53, 45.80),
    "长春": (125.32, 43.90), "长春市": (125.32, 43.90),
    "昆明": (102.83, 24.88), "昆明市": (102.83, 24.88),
    "福州": (119.30, 26.08), "福州市": (119.30, 26.08),
    "南昌": (115.86, 28.68), "南昌市": (115.86, 28.68),
    "合肥": (117.23, 31.82), "合肥市": (117.23, 31.82),
    "南宁": (108.37, 22.82), "南宁市": (108.37, 22.82),
    "贵阳": (106.71, 26.57), "贵阳市": (106.71, 26.57),
    "太原": (112.55, 37.87), "太原市": (112.55, 37.87),
    "石家庄": (114.51, 38.04), "石家庄市": (114.51, 38.04),
    "呼和浩特": (111.75, 40.84), "呼和浩特市": (111.75, 40.84),
    "兰州": (103.83, 36.06), "兰州市": (103.83, 36.06),
    "西宁": (101.78, 36.62), "西宁市": (101.78, 36.62),
    "银川": (106.23, 38.49), "银川市": (106.23, 38.49),
    "乌鲁木齐": (87.62, 43.82), "乌鲁木齐市": (87.62, 43.82),
    "拉萨": (91.17, 29.65), "拉萨市": (91.17, 29.65),
    "海口": (110.20, 20.04), "海口市": (110.20, 20.04),
    # 热门城市
    "苏州": (120.59, 31.30), "无锡": (120.31, 31.57),
    "宁波": (121.54, 29.87), "厦门": (118.08, 24.48),
    "青岛": (120.38, 36.07), "大连": (121.61, 38.91),
    "珠海": (113.58, 22.27), "东莞": (113.75, 23.05),
    "佛山": (113.12, 23.02), "三亚": (109.51, 18.25),
    "桂林": (110.28, 25.29), "丽江": (100.23, 26.86),
    "大理": (100.23, 25.61), "洛阳": (112.45, 34.62),
    "开封": (114.31, 34.80), "威海": (122.12, 37.51),
    "烟台": (121.45, 37.46), "秦皇岛": (119.60, 39.93),
    "黄山": (118.34, 30.19), "张家界": (110.48, 29.12),
    "遵义": (106.93, 27.73), "延安": (109.49, 36.59),
    "玉林": (110.16, 22.63),
}


def _api_url(path: str) -> str:
    host = os.getenv("QWEATHER_API_HOST", _DEFAULT_HOST).rstrip("/")
    return f"{host}{path}"


def _resolve_location(city: str) -> str | None:
    """将城市名解析为 QWeather location 参数（经纬度格式）。

    优先精确匹配，其次尝试去掉尾部"市"字匹配。
    """
    coord = _CITY_COORDS.get(city)
    if coord is not None:
        return f"{coord[0]},{coord[1]}"
    # 去掉尾部"市"再试
    if city.endswith("市"):
        coord = _CITY_COORDS.get(city[:-1])
        if coord is not None:
            return f"{coord[0]},{coord[1]}"
    return None


async def _get_json(url: str, params: dict, api_key: str) -> dict:
    headers = {"X-QW-Api-Key": api_key}
    async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        code = str(data.get("code", ""))
        if code != "200":
            raise httpx.HTTPStatusError(
                f"QWeather API error: code={code}",
                request=resp.request,
                response=resp,
            )
        return data


async def weather_qweather(params: dict) -> dict:
    """通过和风天气 QWeather API 查询指定城市与日期的天气。

    使用内置城市经纬度表将中文城市名转为坐标后查询。

    Args:
        params: {"city": str, "date": str(YYYY-MM-DD)}

    Returns:
        统一天气 schema 字典，含 error 字段表示失败原因。
    """
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        return {
            "city": params.get("city"),
            "date": params.get("date"),
            "source": "QWeather",
            "source_updated_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
            "error": "missing_api_key",
        }

    city = params.get("city")
    date = params.get("date")
    if not city or not date:
        return {
            "city": city,
            "date": date,
            "source": "QWeather",
            "source_updated_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
            "error": "missing city or date",
        }

    location = _resolve_location(city)
    if location is None:
        return {
            "city": city,
            "date": date,
            "source": "QWeather",
            "source_updated_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": False,
            "error": "city_not_found",
        }

    url = _api_url("/v7/weather/3d")
    try:
        weather_data = await _get_json(url, {"location": location}, api_key)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return {
                "city": city, "date": date, "source": "QWeather",
                "source_updated_at": datetime.now(timezone.utc).isoformat(),
                "is_demo": False, "error": "city_not_found",
            }
        return {
            "city": city, "date": date, "source": "QWeather",
            "source_updated_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": False, "error": "weather_fetch_failed",
        }
    except Exception:
        return {
            "city": city, "date": date, "source": "QWeather",
            "source_updated_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": False, "error": "weather_fetch_failed",
        }

    daily_list = weather_data.get("daily") or []

    matched = None
    for day in daily_list:
        if day.get("fxDate") == date:
            matched = day
            break

    if matched is None:
        return {
            "city": city, "date": date, "source": "QWeather",
            "source_updated_at": datetime.now(timezone.utc).isoformat(),
            "is_demo": False, "error": "date_out_of_range",
        }

    temp_low = matched.get("tempMin")
    temp_high = matched.get("tempMax")
    return {
        "city": city,
        "date": date,
        "condition": matched.get("textDay", "未知"),
        "temperature": {
            "low": float(temp_low) if temp_low is not None else None,
            "high": float(temp_high) if temp_high is not None else None,
        },
        "precipitation": float(matched.get("precip", "0") or "0"),
        "wind": f"{matched.get('windDirDay', '')} {matched.get('windScaleDay', '')}级".strip(),
        "source": "QWeather",
        "source_updated_at": datetime.now(timezone.utc).isoformat(),
        "is_demo": False,
    }
