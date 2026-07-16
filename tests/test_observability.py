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


def test_metrics_recorded_on_plan():
    from app.observability.metrics import metrics

    before = metrics.snapshot()["total"]
    service = _build_service()

    async def run():
        result = await service.plan(_plan_request(), "req-x")
        import asyncio
        for _ in range(50):
            await asyncio.sleep(0.5)
            final = service.get_result(result["task_id"])
            if final is not None:
                break
        return result

    anyio.run(run)
    after = metrics.snapshot()
    assert after["total"] >= before + 1


def test_health_probes_dependencies():
    service = _build_service()
    dep = anyio.run(service.health)
    assert dep.available is True
    assert "tools=" in dep.detail
