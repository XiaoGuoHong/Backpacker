import json
import re
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.core.config import Settings


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def complete(self, messages: list[dict], json_mode: bool = False) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "response_format": {"type": "json_object"} if json_mode else None,
                }
                if json_mode
                else {"model": self.model, "messages": messages, "temperature": 0},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text)
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def build_llm(settings: Settings) -> Optional[LLMClient]:
    if not settings.llm_available:
        return None
    return LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)


# 保留兼容入口（旧 orchestrator 可能引用）
def build_recognizer(settings: Settings):
    """行程规划器不再使用 NL 意图识别，返回 None。"""
    return None


def build_answer_generator(settings: Settings):
    """旧回答生成器已移除，返回 None。"""
    return None
