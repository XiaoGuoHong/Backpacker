import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.mcp.sql.validator import SQLRejectedError
from app.mcp.tool import MCPRegistry, MCPToolResult, ToolDefinition
from app.observability.logging import log_event


class MCPConnection(ABC):
    @abstractmethod
    async def call(self, name: str, params: dict[str, Any]) -> MCPToolResult:
        ...

    @abstractmethod
    def definition(self, name: str) -> ToolDefinition | None:
        ...

    @abstractmethod
    def definitions(self) -> list[ToolDefinition]:
        ...


class InProcessMCPConnection(MCPConnection):
    def __init__(self, registry: MCPRegistry):
        self._registry = registry

    def definition(self, name: str) -> ToolDefinition | None:
        return self._registry.get(name)

    def definitions(self) -> list[ToolDefinition]:
        return self._registry.list()

    async def call(self, name: str, params: dict[str, Any]) -> MCPToolResult:
        entry_handler = self._registry.handler(name)
        definition = self._registry.get(name)
        if entry_handler is None or definition is None:
            log_event("mcp_unknown_tool", tool_type=name, status="failed", error_code="E_TOOL_UNAVAILABLE")
            return MCPToolResult(
                status="failed",
                error_code="E_TOOL_UNAVAILABLE",
            )
        timeout = definition.timeout_ms / 1000.0
        start = time.monotonic()
        try:
            raw = entry_handler(params)
            if hasattr(raw, "__await__"):
                raw = await raw
            if not isinstance(raw, dict):
                raw = {"value": raw}
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log_event("mcp_call", tool_type=name, status="success", duration_ms=duration_ms)
            return MCPToolResult(
                status="success",
                content=raw,
                source=raw.get("source"),
                source_updated_at=raw.get("source_updated_at"),
                fetched_at=datetime.now(timezone.utc),
            )
        except asyncio.TimeoutError:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log_event("mcp_timeout", tool_type=name, status="timeout", duration_ms=duration_ms, error_code="E_TOOL_TIMEOUT")
            return MCPToolResult(status="timeout", error_code="E_TOOL_TIMEOUT")
        except SQLRejectedError as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log_event("mcp_sql_rejected", tool_type=name, status="failed", duration_ms=duration_ms,
                      error_code="E_SQL_REJECTED")
            return MCPToolResult(status="failed", error_code="E_SQL_REJECTED", content={"reason": exc.reason})
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log_event("mcp_error", tool_type=name, status="failed", duration_ms=duration_ms, error_code="E_TOOL_UNAVAILABLE")
            return MCPToolResult(
                status="failed", error_code="E_TOOL_UNAVAILABLE"
            )


class StreamableHttpMCPConnection(MCPConnection):
    def __init__(self, url: str, timeout_ms: int = 30000):
        self._url = url
        self._timeout = timeout_ms
        self._definitions: dict[str, ToolDefinition] | None = None

    async def _run(self, coro_factory):
        read_timeout = (self._timeout / 1000.0) + 5.0
        async with streamablehttp_client(
            self._url,
            timeout=self._timeout / 1000.0,
            sse_read_timeout=read_timeout,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                return await coro_factory(session)

    async def _list_definitions(self) -> dict[str, ToolDefinition]:
        if self._definitions is not None:
            return self._definitions

        def factory(session):
            return session.list_tools()

        result = await self._run(factory)
        defs: dict[str, ToolDefinition] = {}
        for tool in result.tools:
            defs[tool.name] = ToolDefinition(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema or {},
                timeout_ms=self._timeout,
            )
        self._definitions = defs
        return defs

    def definition(self, name: str) -> ToolDefinition | None:
        if self._definitions is None:
            return None
        return self._definitions.get(name)

    def definitions(self) -> list[ToolDefinition]:
        if self._definitions is None:
            return []
        return list(self._definitions.values())

    async def call(self, name: str, params: dict[str, Any]) -> MCPToolResult:
        start = time.monotonic()
        try:
            def factory(session):
                return session.call_tool(name, arguments=params)

            response = await self._run(factory)
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log_event("mcp_error", tool_type=name, status="failed", duration_ms=duration_ms,
                      error_code="E_TOOL_UNAVAILABLE")
            return MCPToolResult(status="failed", error_code="E_TOOL_UNAVAILABLE")
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        content: dict[str, Any] = {}
        for item in response.content or []:
            if getattr(item, "type", None) == "text":
                try:
                    parsed = json.loads(item.text)
                    if isinstance(parsed, dict):
                        content.update(parsed)
                except Exception:
                    content.setdefault("text", item.text)
        if getattr(response, "isError", False):
            log_event("mcp_error", tool_type=name, status="failed", duration_ms=duration_ms,
                      error_code="E_TOOL_UNAVAILABLE")
            return MCPToolResult(status="failed", error_code="E_TOOL_UNAVAILABLE", content=content)
        log_event("mcp_call", tool_type=name, status="success", duration_ms=duration_ms)
        return MCPToolResult(
            status="success",
            content=content,
            source=content.get("source"),
            source_updated_at=content.get("source_updated_at"),
            fetched_at=datetime.now(timezone.utc),
        )
