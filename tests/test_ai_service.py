import asyncio
import json
import logging
from types import SimpleNamespace

import httpx2
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

from app.config import Settings
from app.models import ChatLog
from app.services import ai as ai_module
from app.services.ai import (
    AIService,
    AITimeoutError,
    AIUnavailableError,
    AIUpstreamError,
    build_ai_messages,
)


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


def make_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.openai.com/v1/responses")


def make_status_error(error_type, status_code: int, code: str | None = None):
    request = make_request()
    response = httpx2.Response(status_code, request=request)
    body = {"error": {"code": code}} if code else {"error": {}}
    return error_type("OpenAI error", response=response, body=body)


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


@pytest.mark.parametrize(
    ("errors", "expected_error"),
    [
        (
            [APITimeoutError(request=make_request()) for _ in range(4)],
            AITimeoutError,
        ),
        (
            [
                make_status_error(RateLimitError, 429, "rate_limit_exceeded")
                for _ in range(4)
            ],
            AIUnavailableError,
        ),
        (
            [APIConnectionError(request=make_request()) for _ in range(4)],
            AIUpstreamError,
        ),
        (
            [make_status_error(InternalServerError, 500) for _ in range(4)],
            AIUnavailableError,
        ),
    ],
)
def test_transient_errors_retry_three_times_with_exponential_backoff(
    errors,
    expected_error,
) -> None:
    client = FakeClient(errors)
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    service = AIService(make_settings(retries=3), client=client, sleep=fake_sleep)

    with pytest.raises(expected_error):
        asyncio.run(service.generate("question", [], "request-id"))

    assert len(client.responses.calls) == 4
    assert sleeps == [1.0, 2.0, 4.0]


def test_transient_error_can_recover_on_a_later_attempt() -> None:
    client = FakeClient(
        [
            APIConnectionError(request=make_request()),
            SimpleNamespace(output_text="recovered"),
        ]
    )
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    service = AIService(make_settings(), client=client, sleep=fake_sleep)

    result = asyncio.run(service.generate("question", [], "request-id"))

    assert result == "recovered"
    assert len(client.responses.calls) == 2
    assert sleeps == [1.0]


def test_hard_timeout_cancels_a_hanging_client_call() -> None:
    class HangingResponses:
        async def create(self, **_kwargs):
            await asyncio.Event().wait()

    client = SimpleNamespace(responses=HangingResponses())
    settings = make_settings(retries=0)
    settings.openai_timeout_seconds = 0.001
    service = AIService(settings, client=client)

    with pytest.raises(AITimeoutError):
        asyncio.run(service.generate("question", [], "request-id"))


def test_non_retryable_4xx_fails_immediately() -> None:
    error = make_status_error(BadRequestError, 400)
    client = FakeClient([error])
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    service = AIService(make_settings(), client=client, sleep=fake_sleep)

    with pytest.raises(AIUpstreamError):
        asyncio.run(service.generate("question", [], "request-id"))

    assert len(client.responses.calls) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "quota_code",
    [
        "credit_balance_exhausted",
        "insufficient_quota",
        "organization_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    ],
)
def test_quota_rate_limits_fail_immediately_without_retry(quota_code: str) -> None:
    error = make_status_error(RateLimitError, 429, quota_code)
    client = FakeClient([error])
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    service = AIService(make_settings(), client=client, sleep=fake_sleep)

    with pytest.raises(AIUnavailableError):
        asyncio.run(service.generate("question", [], "request-id"))

    assert len(client.responses.calls) == 1
    assert sleeps == []


def test_missing_api_key_is_reported_as_unavailable() -> None:
    service = AIService(make_settings(api_key=""))

    with pytest.raises(AIUnavailableError):
        asyncio.run(service.generate("question", [], "request-id"))


def test_logs_tracking_fields_without_sensitive_content(caplog) -> None:
    secret_question = "private-question-content"
    secret_response = "private-response-content"
    client = FakeClient([SimpleNamespace(output_text=secret_response)])
    service = AIService(make_settings(api_key="private-api-key"), client=client)

    with caplog.at_level(logging.INFO, logger="app.services.ai"):
        result = asyncio.run(
            service.generate(secret_question, [], "tracked-request-id")
        )

    assert result == secret_response
    assert [record.event for record in caplog.records] == [
        "ai_call_started",
        "ai_call_succeeded",
    ]
    assert [json.loads(record.getMessage())["event"] for record in caplog.records] == [
        "ai_call_started",
        "ai_call_succeeded",
    ]
    assert all(record.request_id == "tracked-request-id" for record in caplog.records)
    assert caplog.records[0].question_length == len(secret_question)
    assert caplog.records[1].response_length == len(secret_response)
    rendered_logs = caplog.text
    assert secret_question not in rendered_logs
    assert secret_response not in rendered_logs
    assert "private-api-key" not in rendered_logs
