from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.models import TripRequest


def validate_raw_input(raw: str, settings: Settings) -> str:
    if raw is None:
        raise AppError(
            ErrorCode.INVALID_INPUT,
            "raw_input is required",
            status_code=422,
            public_detail="请输入查询内容",
        )
    cleaned = raw.strip()
    if not cleaned:
        raise AppError(
            ErrorCode.INVALID_INPUT,
            "empty input",
            status_code=422,
            public_detail="查询内容不能为空",
        )
    if len(cleaned) > settings.max_input_length:
        raise AppError(
            ErrorCode.INVALID_INPUT,
            "input too long",
            status_code=413,
            public_detail=f"查询内容过长，请控制在 {settings.max_input_length} 字以内",
        )
    if "\x00" in cleaned:
        raise AppError(
            ErrorCode.INVALID_INPUT,
            "null byte in input",
            status_code=400,
            public_detail="输入包含非法字符",
        )
    return cleaned


def validate_trip_request(req: TripRequest, settings: Settings) -> TripRequest:
    if req.destination and len(req.destination) > settings.max_input_length:
        raise AppError(
            ErrorCode.INVALID_INPUT,
            "destination too long",
            status_code=413,
            public_detail=f"目的地过长，请控制在 {settings.max_input_length} 字以内",
        )
    if req.computed_days > 30:
        raise AppError(
            ErrorCode.INVALID_INPUT,
            "too many days",
            status_code=422,
            public_detail="行程天数不能超过 30 天",
        )
    if "\x00" in req.destination or any("\x00" in i for i in req.interests):
        raise AppError(
            ErrorCode.INVALID_INPUT,
            "null byte in input",
            status_code=400,
            public_detail="输入包含非法字符",
        )
    return req
