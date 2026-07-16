import asyncio

from app.a2a.messages import A2ARequest, A2AResponse
from app.a2a.transport import InProcessA2AConnection, new_task_id


async def _echo(request: A2ARequest) -> A2AResponse:
    return A2AResponse(task_id=request.task_id, status="success", result=request.params)


async def _slow(request: A2ARequest) -> A2AResponse:
    await asyncio.sleep(0.3)
    return A2AResponse(task_id=request.task_id, status="success")


def _make(task_type):
    return A2ARequest(
        request_id="req-1",
        task_id=new_task_id(),
        task_type=task_type,
        params={"city": "北京"},
    )


def test_a2a_dispatch_success():
    import anyio

    async def run():
        conn = InProcessA2AConnection()
        conn.register("weather", _echo)
        resp = await conn.dispatch(_make("weather"))
        assert resp.status == "success"
        assert resp.result["city"] == "北京"

    anyio.run(run)


def test_a2a_unknown_task_type_failed():
    import anyio

    async def run():
        conn = InProcessA2AConnection()
        resp = await conn.dispatch(_make("unknown"))
        assert resp.status == "failed"
        assert resp.error.code == "E_INTENT_UNKNOWN"

    anyio.run(run)


def test_a2a_timeout():
    import anyio

    async def run():
        conn = InProcessA2AConnection(default_timeout_ms=100)
        conn.register("weather", _slow)
        resp = await conn.dispatch(_make("weather"))
        assert resp.status == "timeout"

    anyio.run(run)
