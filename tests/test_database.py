import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.database import create_db_engine, create_schema
from app.models import ChatLog, User
from app.repositories.chat import (
    add_chat,
    delete_user_chats,
    get_recent_chats,
    list_user_chats,
)
from app.repositories.user import add_user, get_user_by_username


def create_user(db: Session, username: str) -> User:
    user = add_user(db, username, "hashed-password")
    db.commit()
    db.refresh(user)
    return user


def test_lifespan_creates_database_schema(test_app) -> None:
    with TestClient(test_app):
        table_names = set(inspect(test_app.state.db_engine).get_table_names())
        user_columns = {
            column["name"]
            for column in inspect(test_app.state.db_engine).get_columns("users")
        }
        request_log_columns = {
            column["name"]
            for column in inspect(test_app.state.db_engine).get_columns("request_logs")
        }

    assert table_names == {"users", "chat_logs", "request_logs"}
    assert "is_admin" in user_columns
    assert {
        "request_id",
        "user_id",
        "chat_id",
        "status_code",
        "latency_ms",
        "error_type",
        "origin",
        "content_type",
        "user_agent",
    } <= request_log_columns


def test_schema_upgrade_adds_admin_role_to_legacy_sqlite_database(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER NOT NULL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO users (id, username, hashed_password, created_at)
            VALUES (1, 'legacy_user', 'legacy-hash', '2026-08-20 00:00:00')
            """
        )

    engine = create_db_engine(f"sqlite:///{database_path}")
    try:
        create_schema(engine)
        user_columns = {
            column["name"] for column in inspect(engine).get_columns("users")
        }
        with engine.connect() as connection:
            is_admin = connection.execute(
                text("SELECT is_admin FROM users WHERE username = 'legacy_user'")
            ).scalar_one()
    finally:
        engine.dispose()

    assert "is_admin" in user_columns
    assert is_admin is False or is_admin == 0


def test_user_repository_adds_and_finds_user(db_session: Session) -> None:
    created = create_user(db_session, "chat_user")

    found = get_user_by_username(db_session, "chat_user")

    assert found is not None
    assert found.id == created.id
    assert found.created_at is not None


def test_recent_chats_return_latest_three_in_chronological_order(
    db_session: Session,
) -> None:
    user = create_user(db_session, "chat_user")
    for number in range(5):
        add_chat(db_session, user.id, f"question-{number}", f"response-{number}")
        db_session.commit()

    recent = get_recent_chats(db_session, user.id, limit=3)

    assert [chat.question for chat in recent] == [
        "question-2",
        "question-3",
        "question-4",
    ]


def test_list_and_delete_chats_are_isolated_by_user(db_session: Session) -> None:
    first_user = create_user(db_session, "first_user")
    second_user = create_user(db_session, "second_user")
    add_chat(db_session, first_user.id, "first question", "first response")
    add_chat(db_session, second_user.id, "second question", "second response")
    db_session.commit()

    deleted_count = delete_user_chats(db_session, first_user.id)
    db_session.commit()

    assert deleted_count == 1
    assert list_user_chats(db_session, first_user.id) == []
    assert [chat.question for chat in list_user_chats(db_session, second_user.id)] == [
        "second question"
    ]
    assert db_session.scalar(select(ChatLog).where(ChatLog.user_id == second_user.id))
