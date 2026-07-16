from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = 5000
    error_types: list[str] = Field(default_factory=list)


class MCPToolResult(BaseModel):
    status: str
    content: dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    source_updated_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    error_code: Optional[str] = None


MCPHandler = Callable[[dict[str, Any]], Any]


@dataclass
class _Entry:
    definition: ToolDefinition
    handler: MCPHandler


class MCPRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, _Entry] = {}

    def register(self, definition: ToolDefinition, handler: MCPHandler) -> None:
        self._tools[definition.name] = _Entry(definition=definition, handler=handler)

    def get(self, name: str) -> ToolDefinition | None:
        entry = self._tools.get(name)
        return entry.definition if entry else None

    def list(self) -> list[ToolDefinition]:
        return [e.definition for e in self._tools.values()]

    def handler(self, name: str) -> MCPHandler | None:
        entry = self._tools.get(name)
        return entry.handler if entry else None
