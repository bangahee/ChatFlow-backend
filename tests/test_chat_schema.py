import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest


def test_chat_question_is_trimmed() -> None:
    request = ChatRequest(question="  안녕하세요  ")

    assert request.question == "안녕하세요"


@pytest.mark.parametrize("question", ["", "   ", "a" * 501])
def test_invalid_chat_question_is_rejected(question: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question=question)


def test_500_character_question_is_allowed() -> None:
    request = ChatRequest(question="a" * 500)

    assert len(request.question) == 500


def test_unknown_chat_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question="hello", admin=True)
