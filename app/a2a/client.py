import asyncio
from typing import Any

from app.a2a.messages import A2ARequest, A2AResponse
from app.a2a.router import A2ARouter
from app.a2a.transport import HttpA2AConnection, InProcessA2AConnection, new_task_id
from app.core.config import Settings


class A2AClient:
    """A2A Client：封装单发/并行派发，支持 HTTP 与 in-process 回退。"""

    def __init__(self, router: A2ARouter | None = None, in_process: InProcessA2AConnection | None = None):
        self.router = router
        self.in_process = in_process

    async def dispatch(self, task_type: str, params: dict[str, Any], request_id: str) -> A2AResponse:
        request = A2ARequest(
            request_id=request_id,
            task_id=new_task_id(),
            task_type=task_type,
            params=params,
        )
        if self.in_process is not None:
            return await self.in_process.dispatch(request)
        if self.router is not None:
            return await self.router.dispatch(request)
        raise RuntimeError("A2AClient 未配置 router 或 in_process")

    async def dispatch_multi(
        self,
        items: list[tuple[str, dict[str, Any]]],
        request_id: str,
    ) -> list[tuple[str, A2AResponse]]:
        tasks = [
            self.dispatch(task_type, params, request_id)
            for task_type, params in items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: list[tuple[str, A2AResponse]] = []
        for (task_type, _), result in zip(items, results):
            if isinstance(result, Exception):
                out.append((task_type, A2AResponse(
                    task_id=new_task_id(),
                    status="failed",
                    error={"code": "E_UPSTREAM_UNAVAILABLE", "message": str(result)},
                )))
            else:
                out.append((task_type, result))
        return out

    async def close(self) -> None:
        if self.router is not None:
            await self.router.close()


def build_a2a_client(settings: Settings) -> A2AClient:
    if settings.a2a_transport == "in-process":
        return A2AClient(in_process=InProcessA2AConnection(default_timeout_ms=settings.a2a_timeout_ms))
    http = HttpA2AConnection(timeout_ms=settings.a2a_timeout_ms)
    router = A2ARouter(settings, http=http)
    return A2AClient(router=router)
