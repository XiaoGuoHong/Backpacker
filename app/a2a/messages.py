from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class A2ARequest(BaseModel):
    request_id: str
    task_id: str
    task_type: str
    version: str = "1.0"
    params: dict[str, Any] = Field(default_factory=dict)
    deadline: Optional[datetime] = None
    trace: dict[str, str] = Field(default_factory=dict)


class A2AError(BaseModel):
    code: str
    message: str


class A2AResponse(BaseModel):
    task_id: str
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    updated_at: Optional[datetime] = None
    error: Optional[A2AError] = None
