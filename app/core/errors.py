from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ErrorCode(str, Enum):
    PARAM_MISSING = "E_PARAM_MISSING"
    INTENT_UNKNOWN = "E_INTENT_UNKNOWN"
    TOOL_TIMEOUT = "E_TOOL_TIMEOUT"
    TOOL_UNAVAILABLE = "E_TOOL_UNAVAILABLE"
    NO_RESULT = "E_NO_RESULT"
    INVALID_INPUT = "E_INVALID_INPUT"
    SQL_REJECTED = "E_SQL_REJECTED"
    RATE_LIMITED = "E_RATE_LIMITED"
    BODY_TOO_LARGE = "E_BODY_TOO_LARGE"
    UPSTREAM_UNAVAILABLE = "E_UPSTREAM_UNAVAILABLE"
    NOT_FOUND = "E_NOT_FOUND"
    INTERNAL = "E_INTERNAL"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        public_detail: Optional[str] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.public_detail = public_detail

    @property
    def public_message(self) -> str:
        return self.public_detail or self.message


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    request_id: Optional[str] = None
    error: ErrorDetail


def build_error_response(request, code: ErrorCode, message: str) -> dict:
    request_id = getattr(request.state, "request_id", None) if request is not None else None
    return ErrorResponse(request_id=request_id, error=ErrorDetail(code=code.value, message=message)).model_dump()
