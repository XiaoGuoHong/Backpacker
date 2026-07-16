import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx

from app.a2a.messages import A2AError, A2ARequest, A2AResponse
from app.observability.logging import log_event

AgentHandler = Callable[[A2ARequest], Awaitable[A2AResponse]]


class A2AConnection(ABC):
    @abstractmethod
    async def dispatch(self, request: A2ARequest) -> A2AResponse:
        ...

    @abstractmethod
    def register(self, task_type: str, handler: AgentHandler) -> None:
        ...


class InProcessA2AConnection(A2AConnection):
    def __init__(self, default_timeout_ms: int = 5000):
        self._handlers: dict[str, AgentHandler] = {}
        self.default_timeout_ms = default_timeout_ms

    def register(self, task_type: str, handler: AgentHandler) -> None:
        self._handlers[task_type] = handler

    async def dispatch(self, request: A2ARequest) -> A2AResponse:
        handler = self._handlers.get(request.task_type)
        if handler is None:
            log_event("a2a_no_agent", task_id=request.task_id, agent_type=request.task_type,
                      status="failed", error_code="E_INTENT_UNKNOWN")
            return A2AResponse(
                task_id=request.task_id,
                status="failed",
                error=A2AError(code="E_INTENT_UNKNOWN", message="no agent for task_type"),
            )
        timeout = self.default_timeout_ms / 1000.0
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(handler(request), timeout=timeout)
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log_event("a2a_dispatch", task_id=request.task_id, agent_type=request.task_type,
                      status=result.status, duration_ms=duration_ms,
                      error_code=(result.error.code if result.error else None))
            return result
        except asyncio.TimeoutError:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log_event("a2a_timeout", task_id=request.task_id, agent_type=request.task_type,
                      status="timeout", duration_ms=duration_ms, error_code="E_TOOL_TIMEOUT")
            return A2AResponse(
                task_id=request.task_id,
                status="timeout",
                error=A2AError(code="E_TOOL_TIMEOUT", message="agent timeout"),
            )
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log_event("a2a_error", task_id=request.task_id, agent_type=request.task_type,
                      status="failed", duration_ms=duration_ms, error_code="E_UPSTREAM_UNAVAILABLE")
            return A2AResponse(
                task_id=request.task_id,
                status="failed",
                error=A2AError(code="E_UPSTREAM_UNAVAILABLE", message="agent error"),
            )


class HttpA2AConnection:
    """通过 HTTP 向 A2A Server 的 /tasks/send 发送请求。"""

    def __init__(self, timeout_ms: int = 12000, retries: int = 1):
        self.timeout_ms = timeout_ms
        self.retries = retries
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_ms / 1000.0 + 5.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def post(self, url: str, request: A2ARequest) -> A2AResponse:
        start = time.monotonic()
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                client = self._ensure_client()
                response = await client.post(
                    url,
                    json=request.model_dump(mode="json"),
                    timeout=self.timeout_ms / 1000.0,
                )
                response.raise_for_status()
                data = response.json()
                duration_ms = round((time.monotonic() - start) * 1000, 1)
                log_event("a2a_http_dispatch", task_id=request.task_id, agent_type=request.task_type,
                          status="success", duration_ms=duration_ms)
                return A2AResponse(**data)
            except httpx.TimeoutException:
                last_exc = httpx.TimeoutException("A2A timeout")
                log_event("a2a_http_timeout", task_id=request.task_id, agent_type=request.task_type,
                          status="timeout", error_code="E_TOOL_TIMEOUT")
            except Exception as exc:
                last_exc = exc
                log_event("a2a_http_error", task_id=request.task_id, agent_type=request.task_type,
                          status="failed", error_code="E_UPSTREAM_UNAVAILABLE")

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        code = "E_TOOL_TIMEOUT" if isinstance(last_exc, httpx.TimeoutException) else "E_UPSTREAM_UNAVAILABLE"
        return A2AResponse(
            task_id=request.task_id,
            status="timeout" if code == "E_TOOL_TIMEOUT" else "failed",
            error=A2AError(code=code, message="A2A 调用失败"),
        )

    async def health(self, url: str) -> bool:
        try:
            client = self._ensure_client()
            resp = await client.get(url.replace("/tasks/send", "/health"), timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False


def new_task_id() -> str:
    return "task-" + uuid.uuid4().hex[:12]


def now() -> datetime:
    return datetime.now(timezone.utc)
