import sqlite3
from pathlib import Path


def test_check_logs_script_returns_recent_user_conversations(tmp_path) -> None:
    database_path = tmp_path / "chatflow.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL
            );
            CREATE TABLE chat_logs (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE request_logs (
                id INTEGER PRIMARY KEY,
                request_id TEXT NOT NULL,
                user_id INTEGER,
                chat_id INTEGER,
                status_code INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                error_type TEXT,
                origin TEXT,
                content_type TEXT,
                user_agent TEXT
            );
            INSERT INTO users (id, username) VALUES (1, 'chat_user');
            INSERT INTO chat_logs
                (id, user_id, question, response, created_at)
            VALUES
                (1, 1, 'older question', 'older response', '2026-08-01T00:00:00Z'),
                (2, 1, 'latest question', 'latest response', '2026-08-02T00:00:00Z');
            INSERT INTO request_logs
                (id, request_id, user_id, chat_id, status_code, latency_ms,
                 error_type, origin, content_type, user_agent)
            VALUES
                (1, 'older-request', 1, 1, 201, 120.5, NULL,
                 'https://frontend.example', 'application/json', 'browser'),
                (2, 'latest-request', 1, 2, 201, 80.25, NULL,
                 'https://frontend.example', 'application/json', 'browser');
            """
        )
        script_path = Path(__file__).parents[1] / "scripts" / "check_logs.sql"
        rows = connection.execute(script_path.read_text(encoding="utf-8")).fetchall()
    finally:
        connection.close()

    assert rows == [
        (
            2,
            1,
            "chat_user",
            "2026-08-02T00:00:00Z",
            "latest question",
            "latest response",
            "latest-request",
            201,
            80.25,
            None,
            "https://frontend.example",
            "application/json",
            "browser",
        ),
        (
            1,
            1,
            "chat_user",
            "2026-08-01T00:00:00Z",
            "older question",
            "older response",
            "older-request",
            201,
            120.5,
            None,
            "https://frontend.example",
            "application/json",
            "browser",
        ),
    ]
