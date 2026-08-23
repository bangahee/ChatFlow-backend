# ChatFlow Backend

React 클라이언트와 분리 배포되는 FastAPI 기반 AI 챗봇 JSON API입니다. 사용자가
안전하게 가입·로그인하고, 이전 대화 문맥을 반영한 AI 답변을 받은 뒤 본인의
대화 기록만 조회하거나 삭제할 수 있도록 합니다.

설치부터 Swagger, Frontend 연동, 테스트와 배포 흐름까지 정리한
[Backend A–Z 사용 가이드](docs/BACKEND_USAGE_GUIDE.md)를 참고해 주세요.

## 문제, 대상 사용자, 핵심 시나리오

- 문제: 단순 AI 호출만으로는 사용자 인증, 대화 연속성, 기록 보관과 장애 추적이
  어렵습니다.
- 대상 사용자: 계정별로 안전하게 AI와 대화하고 기록을 다시 확인하려는 웹 사용자
- 핵심 시나리오: 회원가입 → 로그인 → 질문 전송 → 최근 대화 3개를 포함한 AI 응답
  생성 → 사용자별 DB 저장 → 기록 조회 또는 삭제

## 시스템 구성

```text
React Frontend (Vercel)
        │ HTTPS JSON + Bearer JWT
        ▼
FastAPI Backend (Railway)
  ├── Auth Router / JWT / Argon2
  ├── Chat Router / Service / Repository
  ├── OpenAI Responses API
  ├── Request·AI·DB structured logging
  └── SQLAlchemy → SQLite persistent volume
```

Router는 HTTP 계약, Service는 업무 흐름, Repository는 SQLAlchemy 쿼리를
담당합니다. OpenAI API Key와 JWT Secret은 서버 환경 변수에만 저장합니다.

## 주요 기능

- Argon2 비밀번호 해시와 JWT Bearer 인증
- 사용자별 Chat 기록 저장·조회·삭제
- 최근 대화 최대 3개를 과거→최신 순서로 OpenAI에 전달
- OpenAI timeout, rate limit, 연결 오류와 5xx 재시도
- 오류 유형별 502, 503, 504 응답과 실패 응답 미저장
- 요청 수신부터 AI 호출과 DB 저장, 요청 완료까지 동일 `request_id` 추적
- `/health`, pytest, GitHub Actions, Railway Config as Code

## 로컬 실행

Python 3.13 환경에서 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

- API Base URL: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

## 환경 변수

| 변수 | 설명 | 예시/기본값 |
|---|---|---|
| `APP_ENV` | 실행 환경 | `development` |
| `SECRET_KEY` | JWT 서명용 비밀값 | Production에서는 충분히 긴 임의 문자열 |
| `ALGORITHM` | JWT 알고리즘 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 유효 시간 | `1440` |
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///./chatflow.db` |
| `OPENAI_API_KEY` | 서버 전용 OpenAI API Key | Git에 커밋 금지 |
| `OPENAI_MODEL` | Responses API 모델 | `gpt-5-nano` |
| `OPENAI_TIMEOUT_SECONDS` | AI 시도별 제한 시간 | `20` |
| `OPENAI_MAX_RETRIES` | 최초 호출 이후 추가 재시도 | `3` |
| `CORS_ORIGINS` | 허용 Frontend Origin | 쉼표로 여러 개 설정 가능 |

`.env`, API Key, JWT, 비밀번호와 Production Secret은 Git 또는 로그에 기록하지
않습니다. GitHub Actions는 Mock AI를 사용하므로 Production Secret이 필요하지
않습니다.

## API 명세와 실행 예시

| Method | Endpoint | 인증 | 성공 | 설명 |
|---|---|---:|---:|---|
| `GET` | `/health` | X | 200 | 서버 상태 확인 |
| `POST` | `/api/auth/register` | X | 201 | 회원가입 |
| `POST` | `/api/auth/login` | X | 200 | JWT 발급 |
| `GET` | `/api/me` | O | 200 | 현재 사용자 조회 |
| `POST` | `/api/chat` | O | 201 | AI 응답 생성 및 저장 |
| `GET` | `/api/me/chats` | O | 200 | 내 대화 기록 조회 |
| `DELETE` | `/api/me/chats` | O | 200 | 내 대화 기록 전체 삭제 |

### Health Check

```bash
curl http://localhost:8000/health
```

```json
{"status":"ok"}
```

### 회원가입과 로그인

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"chat_user","password":"password123"}'
```

```json
{"id":1,"username":"chat_user","created_at":"2026-08-23T01:00:00Z"}
```

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"chat_user","password":"password123"}'
```

```json
{"access_token":"<jwt>","token_type":"bearer","expires_in":86400}
```

이후 보호 API에는 `Authorization: Bearer <jwt>` Header를 전달합니다.

### 질문 전송

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <jwt>' \
  -d '{"question":"FastAPI의 장점을 설명해 줘"}'
```

```json
{
  "id": 1,
  "question": "FastAPI의 장점을 설명해 줘",
  "response": "AI 응답 내용",
  "created_at": "2026-08-23T01:05:00Z",
  "request_id": "4de5a3bb-32cf-42b2-a613-d4602dd2e6df"
}
```

서버는 모든 응답에 `X-Request-ID` Header를 추가합니다. Chat 응답 본문의
`request_id`와 같은 값이므로 오류 조사 시 해당 ID로 전체 흐름을 추적할 수
있습니다.

### 기록 확인과 삭제

```bash
curl http://localhost:8000/api/me/chats \
  -H 'Authorization: Bearer <jwt>'
```

```json
{
  "items": [
    {
      "id": 1,
      "question": "FastAPI의 장점을 설명해 줘",
      "response": "AI 응답 내용",
      "created_at": "2026-08-23T01:05:00Z"
    }
  ],
  "count": 1
}
```

```bash
curl -X DELETE http://localhost:8000/api/me/chats \
  -H 'Authorization: Bearer <jwt>'
```

### 주요 오류

| 상태 | 상황 |
|---:|---|
| 400 | 중복 아이디 |
| 401 | 로그인 실패 또는 없거나 만료·변조된 Token |
| 422 | 잘못된 사용자 입력, 공백 질문, 500자 초과 |
| 500 | 회원가입 또는 Chat DB 처리 실패 |
| 502 | OpenAI 연결 또는 응답 형식 오류 |
| 503 | OpenAI Key 미설정, quota 또는 일시적 사용 불가 |
| 504 | OpenAI 최종 timeout |

처리 가능한 오류는 `{"detail":"오류 설명"}` 형태입니다.

## Database

SQLite와 SQLAlchemy 2.0을 사용하며 `User : ChatLog = 1:N` 관계입니다.

```text
users                         chat_logs
├── id PK                 ┌── id PK
├── username UNIQUE       ├── user_id FK → users.id
├── hashed_password       ├── question
└── created_at            ├── response
                          └── created_at
```

| Table | Field | Type/제약 | 설명 |
|---|---|---|---|
| `users` | `id` | PK | 사용자 식별자 |
| `users` | `username` | `VARCHAR(50)`, UNIQUE, INDEX, NOT NULL | 로그인 아이디 |
| `users` | `hashed_password` | `VARCHAR(255)`, NOT NULL | Argon2 해시 |
| `users` | `created_at` | UTC datetime, NOT NULL | 가입 시각 |
| `chat_logs` | `id` | PK | 대화 식별자 |
| `chat_logs` | `user_id` | FK, INDEX, NOT NULL | 대화 소유 사용자 |
| `chat_logs` | `question` | TEXT, NOT NULL | 사용자 질문 |
| `chat_logs` | `response` | TEXT, NOT NULL | AI 응답 |
| `chat_logs` | `created_at` | UTC datetime, INDEX, NOT NULL | 생성 시각 |

서버 lifespan 시작 시 빈 DB에 스키마를 생성합니다. Repository는 쿼리를,
Service는 commit과 rollback을 담당합니다. 현재 MVP에서는 Alembic을 사용하지
않습니다.

DB 저장 결과는 인증된 `GET /api/me/chats`로 확인할 수 있습니다. 배포 환경의
영속성 확인 방법은 [Railway 배포 검증 문서](docs/RAILWAY_DEPLOYMENT.md)를
따릅니다.

## OpenAI 안정성

- 비동기 OpenAI Responses API와 `store=False`를 사용합니다.
- SDK 자체 재시도는 끄고 앱에서 재시도 정책을 관리합니다.
- 최근 대화 최대 3개와 현재 질문을 순서대로 전달합니다.
- Timeout, Rate Limit, 연결 오류와 OpenAI 5xx는 `1, 2, 4초` backoff로
  최대 3회 추가 재시도합니다.
- Quota/Billing 오류와 재시도 불가능한 4xx는 즉시 사용자 오류로 변환합니다.
- AI 실패 또는 빈 응답은 ChatLog로 저장하지 않습니다.

## 운영 로그

운영 로그는 한 줄 JSON이며 다음 순서로 동일 `request_id`를 공유합니다.

```text
request_received
  ├── auth_failed                         # 인증 실패 시
  ├── ai_call_started
  ├── ai_call_succeeded | ai_call_failed
  ├── db_save_succeeded | db_save_failed # DB 저장을 시도한 경우
  └── request_completed
```

로그에는 method, path, 상태 코드, latency, AI 시도 횟수, 질문·응답 길이와
오류 타입만 기록합니다. 비밀번호, JWT, 질문·응답 본문, OpenAI API Key는
기록하지 않습니다.

## 테스트와 CI

테스트는 각 실행마다 임시 SQLite 파일과 Mock OpenAI Client를 사용하므로 운영
DB, 실제 API Key 또는 실제 backoff 대기가 필요하지 않습니다.

```bash
python -m pytest -q
```

GitHub Actions는 `develop`·`main` 대상 Pull Request와 두 브랜치 Push마다
Python 3.13에서 같은 명령을 실행합니다.

## Railway 배포

`railway.json`은 Railpack, Uvicorn 시작 명령, `/health`, 100초 Health timeout과
실패 시 재시작 정책을 설정합니다. 실제 Railway Service에는 다음 값을
등록해야 합니다.

- `APP_ENV=production`
- `SECRET_KEY=<충분히 긴 임의 문자열>`
- `OPENAI_API_KEY=<server-side key>`
- `CORS_ORIGINS=<실제 Vercel Origin>`
- `DATABASE_URL=sqlite:////data/chatflow.db`

Persistent Volume을 `/data`에 Mount해야 SQLite 데이터가 재배포 후에도
유지됩니다. 구체적인 배포·재시작·데이터 영속성 검증과 증빙 항목은
[Railway 배포 검증 문서](docs/RAILWAY_DEPLOYMENT.md)에 정리되어 있습니다.

## 브랜치 전략과 역할

이 저장소는 간소화된 Git Flow를 사용합니다.

```text
feature branch → Pull Request/review → develop → final PR → main
```

| 담당자 | 실제 백엔드 담당 영역 |
|---|---|
| 박주영(A) | FastAPI 기반, Settings, CORS, Schema, 인증·JWT |
| 김승우(B) | SQLAlchemy 모델·Repository, Chat Service/API, DB 테스트 |
| 반가희(C) | OpenAI, timeout/retry, 운영 로그, Health, CI, Railway, 최종 통합 |

`PLANS.md`의 A/B/C 분담을 백엔드 역할 기준으로 사용합니다. Frontend는 별도
저장소에서 관리합니다.
