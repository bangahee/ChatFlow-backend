import asyncio
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.models import ChatLog
from app.services import ai as ai_module
from app.services.ai import AIService, AIUpstreamError, build_ai_messages


class FakeResponses:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes):
        self.responses = FakeResponses(outcomes)


def make_settings(*, retries: int = 3, api_key: str = "test-api-key") -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key=api_key,
        openai_model="test-model",
        openai_timeout_seconds=1,
        openai_max_retries=retries,
    )


def make_chat(number: int) -> ChatLog:
    return ChatLog(
        id=number,
        user_id=1,
        question=f"question-{number}",
        response=f"response-{number}",
    )


def test_context_contains_only_latest_three_chats_in_message_order() -> None:
    messages = build_ai_messages(
        "current-question",
        [make_chat(number) for number in range(1, 5)],
    )

    assert messages[0]["role"] == "system"
    assert messages[1:] == [
        {"role": "user", "content": "question-2"},
        {"role": "assistant", "content": "response-2"},
        {"role": "user", "content": "question-3"},
        {"role": "assistant", "content": "response-3"},
        {"role": "user", "content": "question-4"},
        {"role": "assistant", "content": "response-4"},
        {"role": "user", "content": "current-question"},
    ]


def test_success_uses_responses_api_and_extracts_output_text() -> None:
    client = FakeClient([SimpleNamespace(output_text="  generated answer  ")])
    service = AIService(make_settings(), client=client)

    result = asyncio.run(service.generate("question", [], "request-id"))

    assert result == "generated answer"
    assert client.responses.calls == [
        {
            "model": "test-model",
            "input": build_ai_messages("question", []),
            "store": False,
        }
    ]


def test_production_client_disables_sdk_retries(monkeypatch) -> None:
    client = FakeClient([SimpleNamespace(output_text="answer")])
    captured_options: dict = {}

    def fake_async_openai(**kwargs):
        captured_options.update(kwargs)
        return client

    monkeypatch.setattr(ai_module, "AsyncOpenAI", fake_async_openai)
    service = AIService(make_settings(api_key="configured-api-key"))

    result = asyncio.run(service.generate("question", [], "request-id"))

    assert result == "answer"
    assert captured_options == {
        "api_key": "configured-api-key",
        "timeout": 1.0,
        "max_retries": 0,
    }


@pytest.mark.parametrize("output_text", [None, "", "   ", 123])
def test_empty_or_invalid_output_fails_without_retry(output_text) -> None:
    client = FakeClient([SimpleNamespace(output_text=output_text)])
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    service = AIService(make_settings(), client=client, sleep=fake_sleep)

    with pytest.raises(AIUpstreamError):
        asyncio.run(service.generate("question", [], "request-id"))

    assert len(client.responses.calls) == 1
    assert sleeps == []
