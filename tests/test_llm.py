import anyio

from app.llm.client import LLMClient, build_llm
from app.core.config import Settings


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    async def complete(self, messages, json_mode=False):
        return self.payload


def test_llm_client_complete_returns_payload():
    llm = FakeLLM("hello")
    res = anyio.run(llm.complete, [])
    assert res == "hello"


def test_build_llm_returns_none_without_key():
    settings = Settings()
    assert build_llm(settings) is None


def test_build_llm_returns_client_with_key():
    settings = Settings(llm_api_key="sk-test")
    llm = build_llm(settings)
    assert isinstance(llm, LLMClient)
    assert llm.api_key == "sk-test"
