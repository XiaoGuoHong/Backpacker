from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.a2a.messages import A2AError, A2ARequest, A2AResponse
from app.a2a.transport import now
from app.core.config import Settings
from app.observability.logging import log_event


class A2AServer(ABC):
    """A2A Server 基类：专业 Agent 继承并实现 handle()。"""

    def __init__(self, name: str, task_types: list[str], settings: Settings):
        self.name = name
        self.task_types = task_types
        self.settings = settings

    @abstractmethod
    async def handle(self, request: A2ARequest) -> A2AResponse:
        ...

    async def health(self) -> dict[str, Any]:
        return {"status": "ok", "agent": self.name, "task_types": self.task_types}

    def agent_card(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "task_types": self.task_types,
            "version": "1.0",
            "capabilities": {"mcp": True},
            "health_endpoint": "/health",
        }


def create_a2a_app(server: A2AServer, settings: Settings) -> FastAPI:
    app = FastAPI(title=server.name)

    @app.post("/tasks/send")
    async def tasks_send(request: A2ARequest) -> A2AResponse:
        try:
            return await server.handle(request)
        except Exception as exc:
            log_event("a2a_server_error", task_id=request.task_id, agent_type=request.task_type,
                      status="failed", error_code="E_UPSTREAM_UNAVAILABLE")
            return A2AResponse(
                task_id=request.task_id,
                status="failed",
                error=A2AError(code="E_UPSTREAM_UNAVAILABLE", message="Agent 处理异常"),
            )

    @app.get("/.well-known/agent.json")
    async def agent_card() -> JSONResponse:
        return JSONResponse(server.agent_card())

    @app.get("/health")
    async def health() -> JSONResponse:
        data = await server.health()
        return JSONResponse(data)

    return app
