import asyncio
from dataclasses import dataclass

from app.a2a.client import A2AClient
from app.a2a.messages import A2ARequest, A2AResponse
from app.a2a.transport import new_task_id


@dataclass
class DispatchResult:
    task_type: str
    params: dict
    response: A2AResponse


class OrchestratorAgent:
    def __init__(self, client: A2AClient):
        self.client = client

    async def dispatch(self, task_type: str, params: dict, request_id: str) -> A2AResponse:
        return await self.client.dispatch(task_type, params, request_id)

    async def dispatch_multi(
        self, items: list[tuple[str, dict]], request_id: str
    ) -> list[DispatchResult]:
        """并行派发多个任务，每个独立执行，互不影响。"""
        results = await self.client.dispatch_multi(items, request_id)
        params_map = {task_type: params for task_type, params in items}
        return [
            DispatchResult(task_type=task_type, params=params_map[task_type], response=response)
            for task_type, response in results
        ]
