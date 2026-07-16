import asyncio
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from app.core.config import Settings
from app.main import create_app
from app.mcp.connection import StreamableHttpMCPConnection
from app.mcp.server import build_mcp_server_app


_USED_PORTS = set()


def _free_port() -> int:
    for _ in range(100):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        if port not in _USED_PORTS:
            _USED_PORTS.add(port)
            return port
    raise RuntimeError("no free port")


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _start_server(app, host: str, port: int):
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return thread, server


def _stop_server(pair):
    _, server = pair
    server.should_exit = True


def test_streamable_http_connection_list_and_call():
    port = _free_port()
    mcp_app = build_mcp_server_app(Settings(environment="test", mcp_http_path="/mcp"))
    srv = _start_server(mcp_app, "127.0.0.1", port)
    try:
        assert _wait_for_port("127.0.0.1", port)

        async def main():
            conn = StreamableHttpMCPConnection(f"http://127.0.0.1:{port}/mcp")
            await conn._list_definitions()
            defs = conn.definitions()
            assert any(d.name == "weather_tool" for d in defs)
            res = await conn.call("weather_tool", {"city": "北京", "start_date": "2099-01-01", "days": 1})
            assert res.status == "success"
            assert res.content.get("city")

        asyncio.run(main())
    finally:
        _stop_server(srv)


def test_streamable_http_end_to_end_plan():
    gateway_port = _free_port()
    mcp_port = _free_port()
    url = f"http://127.0.0.1:{mcp_port}/mcp"
    settings = Settings(
        environment="test",
        mcp_transport="streamable-http",
        a2a_transport="in-process",
        amap_mcp_url=url,
        weather_source="demo",
    )
    app = create_app(settings)
    srv = _start_server(app, "127.0.0.1", gateway_port)
    try:
        assert _wait_for_port("127.0.0.1", gateway_port)
        assert _wait_for_port("127.0.0.1", mcp_port)

        resp = httpx.post(
            f"http://127.0.0.1:{gateway_port}/api/v1/plan",
            json={
                "destination": "北京",
                "start_date": "2025-08-11",
                "days": 2,
                "budget_level": "mid",
                "interests": ["历史文化"],
                "hotel_type": "舒适型",
            },
            timeout=20,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["task_id"]
    finally:
        _stop_server(srv)
