import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class GeoPoint(BaseModel):
    lng: float = Field(..., ge=-180, le=180, description="经度")
    lat: float = Field(..., ge=-90, le=90, description="纬度")


class Attraction(BaseModel):
    name: str = Field(..., description="景点名称")
    address: Optional[str] = Field(None, description="地址")
    location: Optional[GeoPoint] = Field(None, description="经纬度")
    rating: Optional[float] = Field(None, ge=0, le=5, description="评分")
    image_url: Optional[str] = Field(None, description="图片链接")
    ticket_price: Optional[float] = Field(None, ge=0, description="门票价格")
    tags: list[str] = Field(default_factory=list, description="标签")
    source: Optional[str] = Field(None, description="数据来源")


class Hotel(BaseModel):
    name: str = Field(..., description="酒店名称")
    address: Optional[str] = Field(None, description="地址")
    location: Optional[GeoPoint] = Field(None, description="经纬度")
    price_per_night: Optional[float] = Field(None, ge=0, description="每晚价格")
    star: Optional[int] = Field(None, ge=1, le=5, description="星级")
    image_url: Optional[str] = Field(None, description="图片链接")
    source: Optional[str] = Field(None, description="数据来源")


class DailyWeather(BaseModel):
    date: datetime.date = Field(..., description="日期")
    day_desc: Optional[str] = Field(None, description="天气描述")
    temp_min: Optional[float] = Field(None, description="最低温度")
    temp_max: Optional[float] = Field(None, description="最高温度")
    precipitation: Optional[float] = Field(None, ge=0, description="降水概率")
    wind: Optional[str] = Field(None, description="风力")
    source: Optional[str] = Field(None, description="数据来源")


class ItineraryDay(BaseModel):
    date: datetime.date = Field(..., description="日期")
    index: int = Field(..., ge=1, description="第几天")
    attractions: list[Attraction] = Field(default_factory=list, description="当日景点")
    hotel: Optional[Hotel] = Field(None, description="当晚酒店")
    weather: Optional[DailyWeather] = Field(None, description="当日天气")


class BudgetBreakdown(BaseModel):
    ticket: float = Field(0.0, ge=0, description="门票")
    hotel: float = Field(0.0, ge=0, description="酒店")
    food: float = Field(0.0, ge=0, description="餐饮")
    transport: float = Field(0.0, ge=0, description="交通")
    total: float = Field(0.0, ge=0, description="总计")
    currency: str = Field("CNY", description="币种")


class Itinerary(BaseModel):
    days: list[ItineraryDay] = Field(..., description="每日行程")
    budget: BudgetBreakdown = Field(..., description="预算明细")
    notes: list[str] = Field(default_factory=list, description="提示/免责声明")
    is_demo: bool = Field(False, description="是否为演示数据")
    sources: list[str] = Field(default_factory=list, description="数据来源列表")


class TripRequest(BaseModel):
    destination: str = Field(..., min_length=1, max_length=128, description="目的地")
    start_date: datetime.date = Field(..., description="开始日期")
    end_date: Optional[datetime.date] = Field(None, description="结束日期")
    days: Optional[int] = Field(None, ge=1, le=30, description="行程天数")
    budget_level: Literal["low", "mid", "high"] = Field(..., description="预算档位")
    interests: list[str] = Field(..., min_length=1, description="兴趣偏好")
    hotel_type: Literal["经济型", "舒适型", "豪华型"] = Field(..., description="酒店类型")

    @field_validator("destination")
    @classmethod
    def _strip_destination(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _validate_dates(self) -> "TripRequest":
        if self.end_date is not None and self.days is not None:
            raise ValueError("end_date 和 days 不能同时提供")
        if self.end_date is None and self.days is None:
            raise ValueError("必须提供 end_date 或 days 其中之一")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date 不能早于 start_date")
        return self

    @property
    def computed_days(self) -> int:
        if self.days is not None:
            return self.days
        if self.end_date is not None:
            return (self.end_date - self.start_date).days + 1
        raise ValueError("无法计算行程天数")

    @property
    def computed_end_date(self) -> datetime.date:
        if self.end_date is not None:
            return self.end_date
        return self.start_date + datetime.timedelta(days=self.computed_days - 1)


class DependencyHealth(BaseModel):
    name: str
    available: bool
    detail: str = ""


class HealthResponse(BaseModel):
    status: str
    app: dict
    dependencies: list[DependencyHealth]
    timestamp: datetime.datetime


# 兼容旧引用（过渡阶段）
class OrchestratorReply(BaseModel):
    status: str
    condition_summary: Optional[str] = None
    results: list[dict[str, Any]] = Field(default_factory=list)
    source: Optional[str] = None
    hints: Optional[str] = None
    answer: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class QueryRequest(BaseModel):
    session_id: Optional[str] = None
    raw_input: str = Field(..., min_length=1)


class UnifiedResultItem(BaseModel):
    type: Optional[str] = None
    content: dict[str, Any] = Field(default_factory=dict)


class UnifiedResponse(BaseModel):
    request_id: str
    session_id: Optional[str] = None
    condition_summary: Optional[str] = None
    results: list[UnifiedResultItem] = Field(default_factory=list)
    source: Optional[str] = None
    query_time: datetime.datetime
    hints: Optional[str] = None
    answer: Optional[str] = None
    status: str = "success"
