import asyncio
import logging

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatLog, User
from app.repositories.chat import add_chat, list_user_chats
from app.repositories.user import add_user
from app.services.ai import AIUnavailableError
from app.services.chat import ChatPersistenceError, create_chat_reply


def create_user(db: Session, username: str = "chat_user") -> User:
    user = add_user(db, username, "hashed-password")
    db.commit()
    db.refresh(user)
    return user


def test_chat_service_passes_latest_three_chats_in_order(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    for number in range(5):
        add_chat(db_session, user.id, f"question-{number}", f"response-{number}")
        db_session.commit()

    captured_questions: list[str] = []

    async def fake_ai(question, history, request_id):
        captured_questions.extend(chat.question for chat in history)
        assert question == "new question"
        assert request_id == "request-id"
        return "new response"

    created = asyncio.run(
        create_chat_reply(
            db_session,
            user,
            "new question",
            "request-id",
            fake_ai,
        )
    )

    assert captured_questions == ["question-2", "question-3", "question-4"]
    assert created.response == "new response"


def test_ai_failure_does_not_save_chat(db_session: Session) -> None:
    user = create_user(db_session)

    async def failing_ai(_question, _history, _request_id):
        raise AIUnavailableError("rate limited")

    with pytest.raises(AIUnavailableError):
        asyncio.run(
            create_chat_reply(
                db_session,
                user,
                "question",
                "request-id",
                failing_ai,
            )
        )

    assert list_user_chats(db_session, user.id) == []


def test_commit_failure_rolls_back_and_session_remains_usable(
    db_session: Session,
    monkeypatch,
    caplog,
) -> None:
    user = create_user(db_session)
    original_commit = db_session.commit

    async def fake_ai(_question, _history, _request_id):
        return "response"

    def fail_commit() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    with caplog.at_level(logging.ERROR, logger="app.services.chat"):
        with pytest.raises(ChatPersistenceError):
            asyncio.run(
                create_chat_reply(
                    db_session,
                    user,
                    "question",
                    "request-id",
                    fake_ai,
                )
            )

    assert len(caplog.records) == 1
    failure_record = caplog.records[0]
    assert failure_record.event == "db_save_failed"
    assert failure_record.request_id == "request-id"
    assert failure_record.operation == "chat_create"
    assert failure_record.error_type == "RuntimeError"
    assert "question" not in caplog.text
    assert "response" not in caplog.text

    monkeypatch.setattr(db_session, "commit", original_commit)
    assert db_session.scalar(select(User).where(User.id == user.id)) is not None
    assert db_session.scalar(select(ChatLog).where(ChatLog.user_id == user.id)) is None
