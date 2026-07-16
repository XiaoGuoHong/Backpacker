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


class TemplatePlanner:
    """规则模板规划器：无 LLM 时的回退。"""

    async def plan(
        self,
        attractions: list[Attraction],
        hotels: list[Hotel],
        weathers: list[DailyWeather],
        request: TripRequest,
    ) -> Itinerary:
        days = request.computed_days
        start_date = request.start_date

        # 按评分排序
        sorted_attractions = sorted(
            [a for a in attractions if a.name],
            key=lambda x: x.rating or 0.0,
            reverse=True,
        )

        # 默认每天 2-3 个景点
        per_day = min(3, max(2, math.ceil(len(sorted_attractions) / max(days, 1))))

        daily_plan: list[ItineraryDay] = []
        for i in range(days):
            d = start_date + datetime.timedelta(days=i)
            day_attractions = sorted_attractions[i * per_day : (i + 1) * per_day]
            weather = next((w for w in weathers if w.date == d), None)
            hotel = hotels[i % len(hotels)] if hotels else None
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
        is_demo = any(a.source == "演示数据" for a in attractions) or not attractions
        sources = list({a.source for a in attractions if a.source})
        if weathers and weathers[0].source:
            sources.append(weathers[0].source)
        sources = list(set(sources))

        return Itinerary(
            days=daily_plan,
            budget=budget,
            notes=["数据仅供参考，具体以官方发布为准。"],
            is_demo=is_demo,
            sources=sources or ["演示数据"],
        )

    def _estimate_budget(self, days: list[ItineraryDay], request: TripRequest) -> BudgetBreakdown:
        level_multipliers = {"low": 0.7, "mid": 1.0, "high": 1.6}
        mul = level_multipliers.get(request.budget_level, 1.0)
        days_count = len(days)

        ticket = 0.0
        for day in days:
            for a in day.attractions:
                if a.ticket_price:
                    ticket += a.ticket_price

        hotel_per_night = {"经济型": 200.0, "舒适型": 400.0, "豪华型": 900.0}.get(request.hotel_type, 400.0)
        hotel = hotel_per_night * max(days_count - 1, 0) * mul

        food = 150.0 * days_count * mul
        transport = 50.0 * days_count * mul
        total = ticket + hotel + food + transport

        return BudgetBreakdown(
            ticket=round(ticket, 2),
            hotel=round(hotel, 2),
            food=round(food, 2),
            transport=round(transport, 2),
            total=round(total, 2),
            currency="CNY",
        )


class LLMPlanner:
    """LLM 规划器：调用 LLM 生成行程，失败时回退到模板。"""

    _SYSTEM = (
        "你是旅行行程规划师。请根据提供的景点、酒店、天气和用户需求，生成一个 JSON 格式的多日行程。\n"
        "要求：\n"
        "1. 每天安排 2-4 个景点，尽量按地理位置邻近安排。\n"
        "2. 每个景点从输入列表中选择，不要编造。\n"
        "3. 每晚分配一个酒店。\n"
        "4. 预算按 low/mid/high 档位估算，包含 ticket、hotel、food、transport、total，单位为 CNY。\n"
        "5. 输出必须是可以解析的 JSON，格式如下：\n"
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

        is_demo = any(a.source == "演示数据" for a in attractions) or not attractions
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
