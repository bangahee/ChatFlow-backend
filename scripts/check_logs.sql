-- ChatFlow conversation log inspection query.
-- Run locally:
--   sqlite3 -header -column ./chatflow.db < scripts/check_logs.sql
-- Run against the Railway volume from its service shell:
--   sqlite3 -header -column /data/chatflow.db < scripts/check_logs.sql

SELECT
    chat_logs.id AS chat_id,
    users.id AS user_id,
    users.username,
    chat_logs.created_at,
    chat_logs.question,
    chat_logs.response,
    request_logs.request_id,
    request_logs.status_code,
    request_logs.latency_ms,
    request_logs.error_type,
    request_logs.origin,
    request_logs.content_type,
    request_logs.user_agent
FROM chat_logs
JOIN users ON users.id = chat_logs.user_id
LEFT JOIN request_logs ON request_logs.chat_id = chat_logs.id
ORDER BY chat_logs.created_at DESC, chat_logs.id DESC
LIMIT 100;
