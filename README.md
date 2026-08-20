# ChatFlow Backend

React 클라이언트와 분리해서 배포하는 FastAPI 기반 JSON API입니다. 회원가입,
JWT 로그인, 현재 사용자 조회, 사용자별 대화 기록과 AI 응답 저장 기능을
제공합니다.

## 실행

Python 3.13 환경에서 의존성을 설치하고 서버를 실행합니다.

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

기본 API 문서는 `http://localhost:8000/docs`에서 확인할 수 있습니다.

## 환경 변수

`.env.example`을 `.env`로 복사한 뒤 실제 값을 설정합니다.

| 변수 | 설명 |
|---|---|
| `SECRET_KEY` | JWT 서명 Key |
| `ALGORITHM` | JWT 알고리즘, 기본 `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 유효 시간 |
| `DATABASE_URL` | SQLAlchemy Database URL |
| `OPENAI_API_KEY` | OpenAI API Key |
| `OPENAI_MODEL` | 사용할 OpenAI 모델 |
| `OPENAI_TIMEOUT_SECONDS` | AI 호출 제한 시간 |
| `OPENAI_MAX_RETRIES` | AI 호출 최대 재시도 수 |
| `CORS_ORIGINS` | 허용할 Frontend Origin, 쉼표로 구분 |

실제 Secret과 API Key는 Git에 커밋하지 않습니다.

## API

| Method | Endpoint | 인증 | 설명 |
|---|---|---:|---|
| `POST` | `/api/auth/register` | X | 회원가입 |
| `POST` | `/api/auth/login` | X | JWT 발급 |
| `GET` | `/api/me` | O | 현재 사용자 조회 |
| `POST` | `/api/chat` | O | AI 질문과 응답 저장 |
| `GET` | `/api/me/chats` | O | 내 대화 기록 조회 |
| `DELETE` | `/api/me/chats` | O | 내 대화 기록 전체 삭제 |

보호 API는 다음 Header가 필요합니다.

```http
Authorization: Bearer <access_token>
```

대화 기록 조회 응답은 다음 구조를 사용합니다.

```json
{
  "items": [
    {
      "id": 1,
      "question": "질문",
      "response": "응답",
      "created_at": "2026-08-20T03:10:00Z"
    }
  ],
  "count": 1
}
```

## Database

- SQLite와 SQLAlchemy 2.0을 사용합니다.
- 서버 lifespan 시작 시 빈 DB에 `users`, `chat_logs` 테이블을 생성합니다.
- `User`와 `ChatLog`는 1:N 관계입니다.
- Repository는 Query만 수행하고 Service가 commit과 rollback을 담당합니다.
- 현재 MVP는 Alembic Migration을 사용하지 않습니다.

## 테스트

테스트는 각 실행마다 임시 SQLite 파일을 사용하며 운영 DB나 실제 OpenAI API를
호출하지 않습니다.

```bash
uv run --with-requirements requirements.txt python -m pytest -q
```

현재 `app/services/ai.py`는 담당자 C가 실제 OpenAI 호출로 교체할 통합
Interface를 제공합니다. 실제 구현이 연결되기 전 `POST /api/chat`은 정상
응답을 가장하지 않고 `503 Service Unavailable`을 반환합니다.
