from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import subprocess
import sys
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from app.a2a.agent import create_attraction_agent, create_hotel_agent, create_weather_agent
from app.a2a.client import A2AClient, build_a2a_client
from app.a2a.server import create_a2a_app
from app.a2a.transport import InProcessA2AConnection
from app.core.config import Settings, get_settings
from app.core.errors import (
    AppError,
    ErrorCode,
    build_error_response,
)
from app.gateway.ratelimit import RateLimiter
from app.gateway.middleware import BodySizeLimitMiddleware, RequestIdMiddleware
from app.gateway.router import router
from app.mcp.connection import InProcessMCPConnection
from app.mcp.registry import build_default_registry
from app.mcp.server import build_mcp_server_app
from app.observability.logging import configure_logging
from app.orchestrator.service import OrchestratorService, build_orchestrator_service


class _ServerRunner:
    """在子进程中运行一个 ASGI 应用，并等待端口就绪。"""

    def __init__(self, app_factory_path: str, host: str, port: int, env: dict | None = None):
        self.app_factory_path = app_factory_path
        self.host = host
        self.port = port
        self.env = env
        self._process: subprocess.Popen | None = None

    def start(self):
        cmd = [
            sys.executable, "-m", "uvicorn",
            self.app_factory_path,
            "--host", self.host,
            "--port", str(self.port),
            "--log-level", "warning",
        ]
        env = {**dict(__import__("os").environ), **(self.env or {})}
        self._process = subprocess.Popen(cmd, env=env)

    async def wait_for_ready(self, timeout: float = 30.0):
        url = f"http://{self.host}:{self.port}/health"
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._process is None or self._process.poll() is not None:
                raise RuntimeError(f"子进程未启动或已退出: {self.app_factory_path}")
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return
            except Exception:
                pass
            await asyncio.sleep(0.2)
        raise RuntimeError(f"等待服务就绪超时: {url}")

    async def stop(self):
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()


class _McpServerRunner:
    """在线程中启动 MCP Server（兼容旧逻辑）。"""

    def __init__(self, app, host: str, port: int):
        import uvicorn
        self._config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self._server = uvicorn.Server(self._config)
        self._thread = None

    def start(self):
        import threading
        def _run():
            try:
                self._server.run()
            except Exception:  # noqa
                pass
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    async def stop(self):
        self._server.should_exit = True


def _wait_for_port(host: str, port: int, timeout: float = 10.0):
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"端口 {host}:{port} 未就绪")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runners: list[_ServerRunner] = []
        mcp_runner: _McpServerRunner | None = None

        if settings.mcp_transport == "streamable-http":
            from urllib.parse import urlparse
            parsed = urlparse(settings.amap_mcp_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 8001
            mcp_app = build_mcp_server_app(settings)
            mcp_runner = _McpServerRunner(mcp_app, host, port)
            mcp_runner.start()
            _wait_for_port(host, port)

        if settings.a2a_transport == "http":
            # 启动三个 Agent Server 子进程
            from urllib.parse import urlparse
            agents = [
                (settings.attraction_agent_url, "app.a2a.attraction_agent_app:app", "ATTRACTION_AGENT"),
                (settings.weather_agent_url, "app.a2a.weather_agent_app:app", "WEATHER_AGENT"),
                (settings.hotel_agent_url, "app.a2a.hotel_agent_app:app", "HOTEL_AGENT"),
            ]
            for url, factory, _ in agents:
                parsed = urlparse(url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 8002
                runner = _ServerRunner(factory, host, port)
                runner.start()
                runners.append(runner)
            for runner in runners:
                await runner.wait_for_ready()

        service = build_orchestrator_service(settings)
        app.state.orchestrator_service = service

        yield

        close_fn = getattr(service.client, "close", None)
        if close_fn is not None:
            result = close_fn()
            if result is not None:
                await result
        for runner in runners:
            await runner.stop()
        if mcp_runner is not None:
            await mcp_runner.stop()

    app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=settings.max_body_bytes)
    app.add_middleware(RequestIdMiddleware)

    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
    app.include_router(router)

    dist_dir = (Path(__file__).parent.parent / "web" / "dist").resolve()
    web_html_path = Path(__file__).parent / "web" / "index.html"
    web_html = web_html_path.read_text(encoding="utf-8") if web_html_path.exists() else "<h1>Backpacker</h1>"

    if dist_dir.is_dir() and (dist_dir / "index.html").is_file():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="web")

        @app.get("/index.html", response_class=HTMLResponse)
        async def index_alt():
            return web_html
    else:

        @app.get("/", response_class=HTMLResponse)
        async def index():
            return web_html

        @app.get("/index.html", response_class=HTMLResponse)
        async def index_alt():
            return web_html

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(request, exc.code, exc.public_message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=build_error_response(request, ErrorCode.INVALID_INPUT, "请求参数不合法"),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=build_error_response(request, ErrorCode.INTERNAL, "服务内部错误"),
        )

    return app


app = create_app()
