# ChatFlow Backend

React 클라이언트와 분리해서 배포하는 FastAPI 기반 JSON API입니다. 회원가입,
JWT 로그인, 현재 사용자 조회, 사용자별 대화 기록과 AI 응답 저장 기능을
제공합니다.

## 실행

Python 3.13 환경에서 의존성을 설치하고 서버를 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
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
| `OPENAI_MAX_RETRIES` | 최초 호출 이후 AI 호출 최대 재시도 수, 기본 `3` |
| `CORS_ORIGINS` | 허용할 Frontend Origin, 쉼표로 구분 |

실제 Secret과 API Key는 Git에 커밋하지 않습니다.

## API

| Method | Endpoint | 인증 | 설명 |
|---|---|---:|---|
| `GET` | `/health` | X | 서버 상태 확인 |
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
python -m pytest -q
```

GitHub Actions도 `develop`과 `main`의 Push 및 Pull Request마다 Python 3.13에서
같은 테스트를 실행합니다. 테스트는 OpenAI Client를 Mock 처리하므로
`OPENAI_API_KEY`가 필요하지 않습니다.

## OpenAI 연동

- 비동기 OpenAI Responses API를 사용합니다.
- 각 요청에는 최근 대화 최대 3개가 과거부터 최신 순서로 포함됩니다.
- Timeout, Rate Limit, 연결 오류와 OpenAI 5xx는 최대 설정 횟수만큼
  exponential backoff 후 재시도합니다.
- AI 호출이 최종 실패하거나 빈 응답을 반환하면 ChatLog를 저장하지 않습니다.
- 로그에는 `request_id`, 시도 횟수와 질문/응답 길이만 기록하며 본문이나 API
  Key를 기록하지 않습니다.

## Railway 배포

저장소의 `railway.json`은 Railpack, Uvicorn 실행 명령과 `/health` Health Check를
설정합니다. Railway Service에는 다음 값을 직접 등록합니다.

- `SECRET_KEY`
- `OPENAI_API_KEY`
- `CORS_ORIGINS`: 실제 Frontend Origin
- `DATABASE_URL`: Persistent Volume 경로와 일치하는 SQLite URL

예를 들어 Volume을 `/data`에 Mount하면
`DATABASE_URL=sqlite:////data/chatflow.db`로 설정합니다. 배포 후 `/health`의 200
응답과 재배포 이후 사용자 및 대화 기록 유지 여부를 확인합니다.
