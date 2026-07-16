import anyio
from datetime import date

from app.core.config import Settings
from app.core.models import TripRequest
from app.orchestrator.service import build_orchestrator_service


def _build_service():
    return build_orchestrator_service(
        Settings(environment="test", mcp_transport="in-process", a2a_transport="in-process")
    )


def _plan_request():
    return TripRequest(
        destination="北京",
        start_date=date(2025, 8, 11),
        days=2,
        budget_level="mid",
        interests=["历史文化"],
        hotel_type="舒适型",
    )


def test_plan_returns_task_id():
    service = _build_service()

    async def run():
        return await service.plan(_plan_request(), "req-x")

    result = anyio.run(run)
    assert result["task_id"]
    assert result["status"] == "accepted"


def test_plan_generates_itinerary():
    service = _build_service()

    async def run():
        result = await service.plan(_plan_request(), "req-x")
        # 轮询等待后台任务完成
        import asyncio
        for _ in range(50):
            await asyncio.sleep(0.5)
            final = service.get_result(result["task_id"])
            if final is not None:
                return final
        return service.get_result(result["task_id"])

    final = anyio.run(run)
    assert final is not None
    assert final["status"] in ("success", "partial")
    assert "itinerary" in final
    assert len(final["itinerary"]["days"]) == 2


def test_plan_result_not_found():
    service = _build_service()
    assert service.get_result("nonexistent") is None


def test_session_save_plan():
    service = _build_service()

    async def run():
        result = await service.plan(_plan_request(), "req-x")
        import asyncio
        await asyncio.sleep(5)
        return service.session_store.get_plan("req-x", result["task_id"])

    stored = anyio.run(run)
    assert stored is not None
    assert "itinerary" in stored
