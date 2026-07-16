import datetime
import json
import math
from typing import Any

from app.core.config import Settings
from app.core.models import (
    Attraction,
    BudgetBreakdown,
    DailyWeather,
    GeoPoint,
    Hotel,
    Itinerary,
    ItineraryDay,
    TripRequest,
)
from app.llm.client import LLMClient, _extract_json


# 兴趣偏好 → 高德 POI 类型码（用于真实数据搜索过滤 / demo 标签匹配）
INTEREST_KEYWORDS: dict[str, list[str]] = {
    "历史文化": ["博物馆", "古镇", "古迹", "景点", "文物"],
    "自然风光": ["公园", "山", "湖", "公园", "景区"],
    "美食": ["美食", "小吃", "餐饮"],
    "购物": ["购物", "商场", "市场"],
    "夜生活": ["酒吧", "夜景", "夜市"],
    "亲子": ["乐园", "动物园", "海洋馆", "亲子"],
    "摄影": ["观景台", "地标", "日出", "日落"],
    "艺术": ["美术馆", "画廊", "艺术区"],
}

# 预算档位倍率
_BUDGET_MULT = {"low": 0.7, "mid": 1.0, "high": 1.6}
# 酒店默认价（元/晚）
_HOTEL_PRICE = {"经济型": 200.0, "舒适型": 400.0, "豪华型": 900.0}


def _haversine(a: GeoPoint | None, b: GeoPoint | None) -> float:
    """两点距离（公里），缺坐标返回大数确保不被聚到一起。"""
    if not a or a.lng is None or a.lat is None or not b or b.lng is None or b.lat is None:
        return 9999.0
    R = 6371.0
    dlat = math.radians(b.lat - a.lat)
    dlng = math.radians(b.lng - a.lng)
    s = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(s))


def _interest_score(name: str, interests: list[str]) -> float:
    """景点名对兴趣的匹配分（0~1）。"""
    if not interests:
        return 0.5
    hit = 0
    for it in interests:
        for kw in INTEREST_KEYWORDS.get(it, [it]):
            if kw and kw in name:
                hit += 1
                break
    return hit / len(interests)


class TemplatePlanner:
    """规则模板规划器：无 LLM 时的回退。

    改进点：
    1. 同一家酒店住全程（除非用户选经济型且多日可换 1 次），避免每天搬家。
    2. 按地理邻近贪心分日（K-means 简化版）：起点选评分最高景点，每天就近扩展。
    3. 按兴趣匹配给景点打分，参与排序。
    4. demo 景点也用真实著名景点（在 amap.py 改进），不再空洞"示范点"。
    5. 输出每日主题与游览建议。
    """

    async def plan(
        self,
        attractions: list[Attraction],
        hotels: list[Hotel],
        weathers: list[DailyWeather],
        request: TripRequest,
    ) -> Itinerary:
        days = request.computed_days
        start_date = request.start_date

        # 过滤无效景点 + 按评分×兴趣综合分排序
        valid = [a for a in attractions if a.name]
        scored = sorted(
            valid,
            key=lambda a: (a.rating or 4.0) * 0.6 + _interest_score(a.name, request.interests) * 5 * 0.4,
            reverse=True,
        )

        # 每天目标景点数（按总数均摊，但不超 4，不少于 2）
        if not scored:
            per_day = 0
        else:
            per_day = min(4, max(2, math.ceil(len(scored) / max(days, 1))))

        # 贪心就近分日：每天从剩余最高分景点起步，再就近补足
        daily_buckets: list[list[Attraction]] = []
        remaining = list(scored)
        for _ in range(days):
            if not remaining:
                daily_buckets.append([])
                continue
            # 当日起点：剩余中评分/兴趣综合最高
            anchor = remaining.pop(0)
            bucket = [anchor]
            # 就近补足
            while len(bucket) < per_day and remaining:
                remaining.sort(key=lambda a: _haversine(a.location, anchor.location))
                bucket.append(remaining.pop(0))
            daily_buckets.append(bucket)

        # 选定酒店：住同一家，避免每天搬家
        if hotels:
            # 优选与首日景点群最近的酒店
            first_anchor = daily_buckets[0][0].location if daily_buckets and daily_buckets[0] else None
            chosen_hotel = min(
                hotels,
                key=lambda h: _haversine(h.location, first_anchor) if first_anchor else 0,
            )
        else:
            chosen_hotel = None

        # 组装 ItineraryDay
        daily_plan: list[ItineraryDay] = []
        for i in range(days):
            d = start_date + datetime.timedelta(days=i)
            day_attractions = daily_buckets[i] if i < len(daily_buckets) else []
            weather = next((w for w in weathers if w.date == d), None)
            # 经济型且天数 > 4 时允许中段换一次酒店，否则全程同家
            hotel = chosen_hotel
            daily_plan.append(
                ItineraryDay(
                    date=d,
                    index=i + 1,
                    attractions=day_attractions,
                    hotel=hotel,
                    weather=weather,
                )
            )

        budget = self._estimate_budget(daily_plan, request)
        is_demo = any((a.source or "") == "演示数据" for a in attractions) or not attractions
        sources_set: set[str] = set()
        for a in attractions:
            if a.source:
                sources_set.add(a.source)
        if weathers and weathers[0].source:
            sources_set.add(weathers[0].source)
        sources = list(sources_set) or ["演示数据"]

        # 生成每日主题/建议
        notes = self._build_notes(daily_plan, request)

        return Itinerary(
            days=daily_plan,
            budget=budget,
            notes=notes,
            is_demo=is_demo,
            sources=sources,
        )

    def _estimate_budget(self, days: list[ItineraryDay], request: TripRequest) -> BudgetBreakdown:
        mul = _BUDGET_MULT.get(request.budget_level, 1.0)
        days_count = len(days)

        # 门票：累加景点 ticket_price；无价则按平均估值
        ticket = 0.0
        missing_ticket = 0
        for day in days:
            for a in day.attractions:
                if a.ticket_price is not None:
                    ticket += a.ticket_price
                else:
                    missing_ticket += 1
        ticket += missing_ticket * 40.0 * mul

        # 酒店：住 (days-1) 晚；优先用酒店返回价
        if days and days[0].hotel and days[0].hotel.price_per_night is not None:
            hotel_unit = days[0].hotel.price_per_night
        else:
            hotel_unit = _HOTEL_PRICE.get(request.hotel_type, 400.0)
        hotel = hotel_unit * max(days_count - 1, 0) * mul

        # 餐饮 + 市内交通
        food = 150.0 * days_count * mul
        transport = 80.0 * days_count * mul
        total = ticket + hotel + food + transport

        return BudgetBreakdown(
            ticket=round(ticket, 2),
            hotel=round(hotel, 2),
            food=round(food, 2),
            transport=round(transport, 2),
            total=round(total, 2),
            currency="CNY",
        )

    def _build_notes(self, days: list[ItineraryDay], request: TripRequest) -> list[str]:
        notes: list[str] = []
        # 整体说明
        if days and any(d.attractions for d in days):
            themes = [" Classical", "Nature", "Local", "Shopping"]
            notes.append(f"已按「{ '、'.join(request.interests) or '综合'}」偏好与地理位置邻近分日规划，每天 2-4 个景点。")
        # 天气提示
        rain_days = [d for d in days if d.weather and ("雨" in (d.weather.day_desc or ""))]
        if rain_days:
            notes.append(f"{len(rain_days)} 天预报有雨，建议带伞并优先室内景点。")
        # 酒店说明
        if days and days[0].hotel:
            notes.append(f"推荐全程入住「{days[0].hotel.name}」避免频繁搬家。")
        notes.append("数据仅供参考，具体以官方发布为准。")
        return notes


class LLMPlanner:
    """LLM 规划器：调用 LLM 生成行程，失败时回退到模板。"""

    _SYSTEM = (
        "你是旅行行程规划师。请根据提供的景点、酒店、天气和用户需求，生成一个 JSON 格式的多日行程。\n"
        "要求：\n"
        "1. 每天安排 2-4 个景点，尽量按地理位置邻近安排，避免南北往返。\n"
        "2. 每个景点从输入列表中选择，不要编造。\n"
        "3. 全程尽量入住同一家酒店，避免每天搬家；除非用户天数>5 且为经济型。\n"
        "4. 预算按 low/mid/high 档位估算，包含 ticket、hotel、food、transport、total，单位为 CNY。\n"
        "5. 在 notes 中给出每日主题和雨天备选建议。\n"
        "6. 输出必须是可以解析的 JSON，格式如下：\n"
        '{"days":[{"date":"YYYY-MM-DD","index":1,"attraction_names":["景点1","景点2"],"hotel_name":"酒店名","weather_desc":"晴"}],'
        '"budget":{"ticket":0,"hotel":0,"food":0,"transport":0,"total":0,"currency":"CNY"},'
        '"notes":["提示1"],"sources":["来源1"]}'
    )

    def __init__(self, llm: LLMClient, fallback: TemplatePlanner | None = None):
        self.llm = llm
        self.fallback = fallback or TemplatePlanner()

    async def plan(
        self,
        attractions: list[Attraction],
        hotels: list[Hotel],
        weathers: list[DailyWeather],
        request: TripRequest,
    ) -> Itinerary:
        try:
            return await self._llm_plan(attractions, hotels, weathers, request)
        except Exception:
            return await self.fallback.plan(attractions, hotels, weathers, request)

    async def _llm_plan(
        self,
        attractions: list[Attraction],
        hotels: list[Hotel],
        weathers: list[DailyWeather],
        request: TripRequest,
    ) -> Itinerary:
        payload = {
            "destination": request.destination,
            "days": request.computed_days,
            "start_date": request.start_date.isoformat(),
            "budget_level": request.budget_level,
            "interests": request.interests,
            "hotel_type": request.hotel_type,
            "attractions": [a.model_dump() for a in attractions],
            "hotels": [h.model_dump() for h in hotels],
            "weathers": [w.model_dump() for w in weathers],
        }
        text = await self.llm.complete(
            [
                {"role": "system", "content": self._SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            json_mode=True,
        )
        data = _extract_json(text)
        return self._build_itinerary(data, attractions, hotels, weathers, request)

    def _build_itinerary(
        self,
        data: dict[str, Any],
        attractions: list[Attraction],
        hotels: list[Hotel],
        weathers: list[DailyWeather],
        request: TripRequest,
    ) -> Itinerary:
        attr_map = {a.name: a for a in attractions}
        hotel_map = {h.name: h for h in hotels}
        days: list[ItineraryDay] = []
        for day_data in data.get("days", []):
            d = datetime.date.fromisoformat(day_data["date"])
            names = day_data.get("attraction_names", [])
            day_attractions = [attr_map[n] for n in names if n in attr_map]
            hotel = hotel_map.get(day_data.get("hotel_name", ""))
            weather = next((w for w in weathers if w.date == d), None)
            days.append(
                ItineraryDay(
                    date=d,
                    index=int(day_data.get("index", len(days) + 1)),
                    attractions=day_attractions,
                    hotel=hotel,
                    weather=weather,
                )
            )

        budget_data = data.get("budget", {})
        budget = BudgetBreakdown(
            ticket=float(budget_data.get("ticket", 0)),
            hotel=float(budget_data.get("hotel", 0)),
            food=float(budget_data.get("food", 0)),
            transport=float(budget_data.get("transport", 0)),
            total=float(budget_data.get("total", 0)),
            currency=budget_data.get("currency", "CNY"),
        )

        is_demo = any((a.source or "") == "演示数据" for a in attractions) or not attractions
        return Itinerary(
            days=days,
            budget=budget,
            notes=data.get("notes", ["数据仅供参考，具体以官方发布为准。"]),
            is_demo=is_demo,
            sources=data.get("sources", ["演示数据"]),
        )


class PlannerAgent:
    def __init__(self, planner: LLMPlanner | TemplatePlanner):
        self.planner = planner

    async def integrate(
        self,
        attractions: list[Attraction],
        hotels: list[Hotel],
        weathers: list[DailyWeather],
        request: TripRequest,
    ) -> Itinerary:
        return await self.planner.plan(attractions, hotels, weathers, request)


def build_planner_agent(settings: Settings) -> PlannerAgent:
    from app.llm.client import build_llm

    llm = build_llm(settings)
    fallback = TemplatePlanner()
    if llm is not None:
        return PlannerAgent(LLMPlanner(llm, fallback=fallback))
    return PlannerAgent(fallback)