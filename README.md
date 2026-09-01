# ChatFlow Backend

React 클라이언트와 분리 배포되는 FastAPI 기반 AI 챗봇 JSON API입니다. 사용자가
안전하게 가입·로그인하고, 이전 대화 문맥을 반영한 AI 답변을 받은 뒤 본인의
대화 기록만 조회하거나 삭제할 수 있도록 합니다.

설치부터 Swagger, Frontend 연동, 테스트와 배포 흐름까지 정리한
[Backend A–Z 사용 가이드](docs/BACKEND_USAGE_GUIDE.md)를 참고해 주세요.

## 저장소와 배포 주소

- Backend Repository: [ChatFlow Backend](https://github.com/bangahee/ChatFlow-backend)
- Frontend Repository: [ChatFlow Frontend](https://github.com/bangahee/ChatFlow)
- Railway Backend: [chatflow-backend-production-b90c.up.railway.app](https://chatflow-backend-production-b90c.up.railway.app)
- Vercel Frontend: [chat-flow-topaz.vercel.app](https://chat-flow-topaz.vercel.app)

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

### 파일과 컴포넌트 역할

```text
app/
├── main.py                  FastAPI 생성, Middleware 설정, Router 등록
├── config.py                환경 변수와 Settings 검증
├── database.py              SQLAlchemy Engine, Session, 초기 Schema 생성
├── dependencies.py          DB Session, JWT 사용자, AI 의존성 제공
├── models.py                User, ChatLog ORM 모델
├── observability.py         request_id 기반 구조화 요청 로그
├── routers/
│   ├── auth.py              회원가입·로그인·현재 사용자 API
│   ├── chat.py              질문 생성·내 기록 조회·전체 삭제 API
│   ├── admin.py             관리자 사용자·대화 조회 API
│   └── health.py            외부 Health Check
├── schemas/                 Pydantic 요청·응답·오류 Schema
├── repositories/            DB Query와 ChatRepository 인터페이스
└── services/                인증, Chat Transaction, OpenAI 업무 흐름
```

웹 UI는 Backend 내부 Template Router가 아니라 별도 Frontend 저장소의
`src/pages`와 `src/components`에 있습니다. `RegisterPage`·`LoginPage`는 인증 UI,
`ChatPage`는 일반 사용자 질문·기록 UI, `AdminPage`는 운영 조회 UI를 담당합니다.
따라서 Backend Router는 JSON API 계약만 담당하고 UI Route는 React Router가
담당합니다.

## 주요 기능

- Argon2 비밀번호 해시와 JWT Bearer 인증
- 사용자별 Chat 기록 저장·조회·삭제
- 관리자 전용 일반 사용자 목록 및 사용자별 전체 대화 조회(조회 전용)
- 최근 대화 최대 3개를 과거→최신 순서로 OpenAI에 전달
- OpenAI timeout, rate limit, 연결 오류와 5xx 재시도
- 오류 유형별 502, 503, 504 응답과 실패 응답 미저장
- 요청 수신부터 AI 호출과 DB 저장, 요청 완료까지 동일 `request_id` 추적
- `request_logs`에 처리 상태·응답 시간·안전한 요청 Metadata 영속화
- `/health`, pytest, GitHub Actions, Railway Config as Code

## Frontend UI와 인증 상태 증빙

웹 UI는 별도 [Frontend Repository](https://github.com/bangahee/ChatFlow)에서
관리합니다. 주요 화면과 자동 검증 위치는 다음과 같습니다.

| 평가 흐름 | 구현 및 검증 |
|---|---|
| 회원가입 | [RegisterPage.tsx](https://github.com/bangahee/ChatFlow/blob/main/src/pages/RegisterPage.tsx) |
| 로그인 | [LoginPage.tsx](https://github.com/bangahee/ChatFlow/blob/main/src/pages/LoginPage.tsx) |
| 질문 입력·AI 응답 | [ChatPage.tsx](https://github.com/bangahee/ChatFlow/blob/main/src/pages/ChatPage.tsx) |
| 내 대화 기록 조회·삭제 | [ChatPage.tsx](https://github.com/bangahee/ChatFlow/blob/main/src/pages/ChatPage.tsx) |
| 사용자 흐름 테스트 | [App.test.tsx](https://github.com/bangahee/ChatFlow/blob/main/src/App.test.tsx) |

이 프로젝트는 서버 메모리에 로그인 상태를 저장하는 Stateful Session 대신
Stateless JWT Bearer 인증을 사용합니다. 로그인 성공 시 Frontend가 Access Token을
저장하고, 새로고침 시 `GET /api/me`로 사용자와 만료 여부를 다시 확인합니다.
보호 API가 `401`을 반환하면 Token을 제거하고 로그인 화면으로 이동합니다. 따라서
서버를 여러 Instance로 확장해도 별도 Session Store 없이 동일한 인증 정책을
유지할 수 있습니다.

따라서 `SessionMiddleware`는 등록하지 않습니다. 인증 확인은 재사용 가능한 FastAPI
`Depends(get_current_user)`로 분리하며, 관리자와 일반 Chat 사용자는 이 의존성을
각각 확장한 `get_current_admin`, `get_current_chat_user`로 제한합니다.

평가항목에서 `SessionMiddleware` 등록 여부를 확인하는 경우, 해당 부분은 서버 세션
방식을 선택했을 때의 구현 기준입니다. 이 프로젝트는 평가항목이 허용하는 JWT 방식을
선택했으므로 `SessionMiddleware`를 사용하지 않고, 인증 상태 복원과 접근 제어는
Frontend의 Token 저장소와 Backend의 `Depends` 의존성으로 동일한 요구를 충족합니다.

비로그인 사용자의 Chat과 기록 접근을 제한하는 이유는 질문·응답이 사용자별 개인
데이터이고, 최근 기록이 다음 AI 요청의 문맥으로 사용되기 때문입니다. 인증 없이
접근을 허용하면 기록 소유권을 확인할 수 없어 다른 사용자의 대화가 노출되거나 잘못된
문맥이 전달될 수 있습니다.

일반 사용자의 기록 조회·추적은 인증된 `GET /api/me/chats`와 Frontend의 내 대화
기록 화면으로 제한됩니다. 별도 관리자 권한을 가진 계정은 채팅 API를 사용할 수
없고, 관리자 API를 통해 일반 사용자와 선택 사용자의 대화 기록만 조회할 수 있습니다.

회원가입 서버 처리 순서는 다음과 같습니다.

```text
POST /api/auth/register
  → RegisterRequest Pydantic 형식 검증
  → 중복 username 확인
  → Argon2 비밀번호 Hash 생성
  → User 생성 및 Transaction commit
  → 비밀번호를 제외한 201 RegisterResponse 반환
```

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
| `LOG_LEVEL` | 애플리케이션 로그 레벨 | `INFO` |
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
| `POST` | `/api/chat` | 일반 사용자 | 201 | AI 응답 생성 및 저장 |
| `GET` | `/api/me/chats` | 일반 사용자 | 200 | 내 대화 기록 조회 |
| `DELETE` | `/api/me/chats` | 일반 사용자 | 200 | 내 대화 기록 전체 삭제 |
| `GET` | `/api/admin/users` | 관리자 | 200 | 일반 사용자와 대화 수 조회 |
| `GET` | `/api/admin/users/{user_id}/chats` | 관리자 | 200 | 일반 사용자의 전체 대화 조회 |

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
{"id":1,"username":"chat_user","is_admin":false,"created_at":"2026-08-23T01:00:00Z"}
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
| 403 | 관리자 계정의 사용자 채팅 API 접근 또는 관리자 권한 없음 |
| 422 | 잘못된 사용자 입력, 공백 질문, 500자 초과 |
| 500 | 회원가입 또는 Chat DB 처리 실패 |
| 502 | OpenAI 연결 또는 응답 형식 오류 |
| 503 | OpenAI Key 미설정, quota 또는 일시적 사용 불가 |
| 504 | OpenAI 최종 timeout |

처리 가능한 오류는 `{"detail":"오류 설명"}` 형태입니다.

실제 실패 응답 예시는 다음과 같습니다.

인증 정보가 없는 보호 API 요청:

```json
{
  "detail": "로그인이 필요합니다."
}
```

유효하지 않거나 만료된 Token:

```json
{
  "detail": "인증 자격 증명이 유효하지 않거나 만료되었습니다."
}
```

질문 길이 또는 형식 검증 실패:

```json
{
  "detail": [
    {
      "type": "string_too_long",
      "loc": ["body", "question"],
      "msg": "String should have at most 500 characters",
      "input": "<500자를 초과한 질문>",
      "ctx": {"max_length": 500}
    }
  ]
}
```

OpenAI 응답 처리 실패:

```json
{
  "detail": "AI 서비스 응답 처리 중 오류가 발생했습니다."
}
```

사용자에게 노출하는 서비스 오류는 HTTP 상태와 `detail`을 공통 계약으로 사용하고
한국어 존댓말 문장으로 통일합니다. 내부 예외명·Stack Trace·Secret은 응답에 노출하지
않습니다. 현재 지원 언어는 한국어이며, 다국어가 필요해지면 상태 코드와 안정적인 내부
오류 식별자는 유지하고 Frontend의 메시지 사전에서 Locale별 문구를 선택합니다.

### API 호환성과 Version 정책

- 현재 공개 계약은 `/api`의 Version 1로 간주합니다.
- 선택 필드나 새 Endpoint처럼 기존 Client를 깨지 않는 변경은 현재 경로에 추가합니다.
- 필드 삭제·이름 변경·의미 변경처럼 호환되지 않는 변경은 `/api/v2`에서 제공하며
  기존 Version은 사전 공지한 기간 동안 유지합니다.
- API 변경 PR은 Pydantic Schema, OpenAPI 응답, Backend 테스트, Frontend Type과
  README 예시를 함께 수정해야 합니다.
- 현재 `/api/me/chats`는 로그인 사용자의 전체 ChatLog Collection이며, 다중 대화방이
  필요해질 경우 `/api/conversations`와 `/api/conversations/{id}`를 새 Version 또는
  호환 가능한 Resource로 설계합니다.

## 관리자 조회

관리자는 `/api/me` 응답의 `is_admin`이 `true`인 계정만 사용할 수 있습니다. 일반
회원가입으로는 관리자 권한이 부여되지 않으며, 권한을 변경하는 HTTP API도 제공하지
않습니다.

기존 사용자를 최초 관리자로 지정할 때는 Backend와 같은 환경 변수 및 DB를 사용하는
운영 Shell에서 아래 명령을 한 번 실행합니다. 대상 사용자는 먼저 회원가입되어 있어야
하며, 명령을 다시 실행해도 안전합니다.

```bash
python -m scripts.grant_admin <username>
```

관리자는 채팅용 계정이 아닌 운영 전용 계정입니다. `POST /api/chat` 및
`GET`·`DELETE /api/me/chats`는 관리자 계정에 `403`을 반환합니다. 관리자 목록과
대화 상세에서는 모든 관리자 계정을 제외하며, 관리자 계정을 대상으로 한 대화 조회는
`404`를 반환합니다. 조회 API에는 검색, 페이지네이션, 수정, 삭제, 내보내기 기능이
없으며, 대화 본문은 서버 로그에 기록하지 않습니다.

## Database

SQLite와 SQLAlchemy 2.0을 사용합니다. `User : ChatLog = 1:N`,
`User : RequestLog = 1:N`이며 성공한 Chat 요청은 `RequestLog.chat_id`로 저장된
질문·AI 응답과 운영 Metadata를 연결합니다.

평가항목에서 표현한 `conversations` Table·Resource는 이 프로젝트의 `chat_logs`에
해당합니다. `chat_logs`의 한 Row가 한 번의 사용자 질문과 AI 응답을 나타내며,
`user_id`를 통해 사용자별 대화 기록을 추적합니다.

```text
users                         chat_logs
├── id PK                 ┌── id PK
├── username UNIQUE       ├── user_id FK → users.id
├── hashed_password       ├── question
├── is_admin              ├── response
└── created_at            └── created_at

request_logs
├── id PK
├── request_id UNIQUE
├── user_id FK → users.id (nullable)
├── chat_id FK → chat_logs.id (nullable)
├── method / path / status_code / latency_ms
├── origin / content_type / user_agent
├── error_type
└── created_at
```

| Table | Field | Type/제약 | 설명 |
|---|---|---|---|
| `users` | `id` | PK | 사용자 식별자 |
| `users` | `username` | `VARCHAR(50)`, UNIQUE, INDEX, NOT NULL | 로그인 아이디 |
| `users` | `hashed_password` | `VARCHAR(255)`, NOT NULL | Argon2 해시 |
| `users` | `is_admin` | `BOOLEAN`, NOT NULL, 기본값 `false` | 관리자 조회 권한 |
| `users` | `created_at` | UTC datetime, NOT NULL | 가입 시각 |
| `chat_logs` | `id` | PK | 대화 식별자 |
| `chat_logs` | `user_id` | FK, INDEX, NOT NULL | 대화 소유 사용자 |
| `chat_logs` | `question` | TEXT, NOT NULL | 사용자 질문 |
| `chat_logs` | `response` | TEXT, NOT NULL | AI 응답 |
| `chat_logs` | `created_at` | UTC datetime, INDEX, NOT NULL | 생성 시각 |
| `request_logs` | `request_id` | `VARCHAR(36)`, UNIQUE, INDEX | 요청 추적 ID |
| `request_logs` | `user_id` | FK, nullable, INDEX | 인증된 사용자 |
| `request_logs` | `chat_id` | FK, nullable, INDEX | 성공한 ChatLog 연결 |
| `request_logs` | `method`, `path` | 문자열 | HTTP 요청 Resource |
| `request_logs` | `status_code` | 정수, INDEX | 최종 처리 상태 |
| `request_logs` | `latency_ms` | 실수 | Backend 응답 시간 |
| `request_logs` | `origin`, `content_type`, `user_agent` | nullable 문자열 | Allow-list 요청 Header Metadata |
| `request_logs` | `error_type` | nullable 문자열 | `HTTP_401` 등 오류 분류 |
| `request_logs` | `created_at` | UTC datetime, INDEX | 처리 기록 시각 |

서버 lifespan 시작 시 빈 DB에 스키마를 생성합니다. Repository는 쿼리를,
Service는 commit과 rollback을 담당합니다. 현재 MVP에서는 Alembic을 사용하지
않습니다. `create_all()`은 빈 DB 생성만 담당하며 기존 Table의 Column을 자동으로
변경하지 않습니다. 이번 운영 감사 기능은 기존 Column을 변경하지 않고 독립적인
`request_logs` Table을 추가하므로 현재 Volume DB에서도 서버 시작 시 안전하게
생성됩니다.

### Schema 변경과 Migration 절차

운영 Schema를 변경하는 PR은 다음 절차를 따릅니다.

1. 변경 전 `/data/chatflow.db`를 Railway Volume 안의 별도 파일로 Backup합니다.
2. 변경 내용을 적용하는 Versioned SQL 또는 Alembic Migration을 PR에 포함합니다.
3. 운영 DB 사본에서 Migration과 현재 전체 테스트를 먼저 실행합니다.
4. 배포 전 쓰기 요청을 중지하고 운영 DB에 Migration을 한 번만 적용합니다.
5. 배포 후 `/health`, 로그인, Chat 저장과 기존 기록 조회를 확인합니다.
6. 실패하면 Service를 중지하고 Backup DB를 복원한 뒤 이전 Release로 Rollback합니다.

SQLite Backup 예시는 다음과 같습니다. 날짜 부분은 실제 작업 시각으로 바꿉니다.

```bash
sqlite3 /data/chatflow.db ".backup '/data/chatflow-backup-YYYYMMDD-HHMM.db'"
```

운영 Schema 변경을 `create_all()`만으로 처리하거나 기존 Volume DB를 삭제해서
적용하지 않습니다.

DB 저장 결과는 인증된 `GET /api/me/chats`로 확인할 수 있습니다. 배포 환경의
영속성 확인 방법은 [Railway 배포 검증 문서](docs/RAILWAY_DEPLOYMENT.md)를
따릅니다.

### SQL로 대화 로그 확인

`scripts/check_logs.sql`은 `users`, `chat_logs`, `request_logs`를 연결하여 최근 대화
100개의 사용자, 생성 시각, 질문·AI 응답, 처리 상태·응답 시간과 안전한 요청
Metadata를 최신순으로 조회합니다. 운영 감사 기능 도입 전 생성된 기존 ChatLog도
`LEFT JOIN`으로 계속 조회됩니다.

로컬 DB:

```bash
sqlite3 -header -column ./chatflow.db < scripts/check_logs.sql
```

Railway Service Shell의 Volume DB:

```bash
sqlite3 -header -column /data/chatflow.db < scripts/check_logs.sql
```

이 SQL과 사용자·관리자 조회 API는 장애 발생 시 `request_id` 주변 시각의 저장 결과를
확인하고, 사용자별 이용 흐름과 반복 오류를 추적하며, 개인정보를 로그에 복제하지 않고
서비스 품질 개선에 필요한 대화 기록을 점검하는 용도로 사용합니다. 운영자가 조회한
질문·응답 원문은 Secret과 동일하게 외부 Issue·PR·Screenshot에 게시하지 않습니다.

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

로그에는 method, path, 상태 코드, latency, AI 시도 횟수, 질문·응답 길이, 오류
타입과 allow-list 방식으로 선택한 `Origin`·`Content-Type`·`User-Agent`만
기록합니다. `Authorization`·Cookie를 포함한 나머지 Header, 비밀번호, JWT,
질문·응답 본문과 OpenAI API Key는 기록하지 않습니다.

대화 원문은 접근 제어가 적용된 `chat_logs`에 저장합니다. 처리 상태·오류·응답 시간과
Allow-list Header Metadata는 `request_logs`와 Railway 구조화 Application Log에
저장하고, 성공한 Chat은 `chat_id`로 두 Table을 연결합니다. `/health`는 DB에 의존하지
않고 감사 기록에서도 제외합니다. 오류 요청의 사용자 입력, `Authorization`, Cookie를
DB에 보관하지 않아 실패 데이터와 인증정보의 불필요한 영속화를 막습니다. 기록은
`request_id`, 발생 시각, 사용자 ID로 추적합니다.

- DB 저장 성공·실패 구현: [app/services/chat.py](https://github.com/bangahee/ChatFlow-backend/blob/main/app/services/chat.py)
- DB 저장 실패와 rollback 검증: [tests/test_chat_service.py](https://github.com/bangahee/ChatFlow-backend/blob/main/tests/test_chat_service.py)
- 요청·인증 로그 검증: [tests/test_observability.py](https://github.com/bangahee/ChatFlow-backend/blob/main/tests/test_observability.py)

## 테스트와 CI

테스트는 각 실행마다 임시 SQLite 파일과 Mock OpenAI Client를 사용하므로 운영
DB, 실제 API Key 또는 실제 backoff 대기가 필요하지 않습니다.

```bash
python -m pytest -q
```

현재 구현 기준 결과는 `124 passed`입니다.

GitHub Actions는 `develop`·`main` 대상 Pull Request와 두 브랜치 Push마다
Python 3.13에서 같은 명령을 실행합니다.

## Railway 배포

`railway.json`은 Railpack, Uvicorn 시작 명령, `/health`, 100초 Health timeout과
실패 시 재시작 정책을 설정합니다. 실제 Railway Service에는 다음 값을
등록해야 합니다.

- `APP_ENV=production`
- `LOG_LEVEL=INFO`
- `SECRET_KEY=<충분히 긴 임의 문자열>`
- `OPENAI_API_KEY=<server-side key>`
- `CORS_ORIGINS=<실제 Vercel Origin>`
- `DATABASE_URL=sqlite:////data/chatflow.db`

Persistent Volume을 `/data`에 Mount해야 SQLite 데이터가 재배포 후에도
유지됩니다. 구체적인 배포·재시작·데이터 영속성 검증과 증빙 항목은
[Railway 배포 검증 문서](docs/RAILWAY_DEPLOYMENT.md)에 정리되어 있습니다.

### Production 최종 검증

| 항목 | 결과 |
|---|---|
| 외부 접근성 재확인 | 2026-09-02 Vercel `200`, Railway `GET /health` → `200 {"status":"ok"}` |
| Backend Repository | 최신 [`main` Branch](https://github.com/bangahee/ChatFlow-backend/tree/main), [PR #28 develop→main](https://github.com/bangahee/ChatFlow-backend/pull/28) 병합 완료 |
| Backend 자동 검증 | 최신 Release Source 기준 pytest `124 passed` |
| Backend 전체 운영 검증 기준 | 실행 코드 `e664343`(PR #23), Deployment `8d4705df` |
| Frontend Repository | `main` `bd67bc4`, [PR #25 입력 초기화 수정](https://github.com/bangahee/ChatFlow/pull/25) 병합 완료 |
| Frontend 자동 검증 | 최신 `main` 기준 lint, 테스트 `31 passed`, Production build 통과 |
| CORS | Vercel Origin의 Login Preflight `200` 및 허용 Origin Header 확인 |
| 사용자 흐름 | 회원가입 `201` → 로그인 `200` → 실제 OpenAI Chat `201` → 기록 조회 성공 |
| 관리자 흐름 | 관리자 로그인 → 사용자 목록·사용자별 대화 조회 `200` |
| 인증 복원 | Frontend 새로고침 후 로그인 상태와 기록 유지 |
| 운영 로그 | 동일 `request_id`로 요청·AI·DB 저장·완료 이벤트 연결 확인 |
| Timeout/Retry | AI timeout 4회 시도 후 `504` 변환 확인 |
| SQLite 영속성 | Railway Container 재시작 후 동일 Chat과 AI 응답 유지 |
| Frontend 오류 | 검증 중 Browser Console Error 없음 |

2026-08-29에 실행 코드 `e664343`을 기준으로 전체 기능과 영속성을 검증했습니다.
이후 변경 사항은 Backend pytest 124개와 Frontend lint·테스트 31개·Production build로
검증했고, 2026-09-02에 두 배포 URL의 외부 접근성을 다시 확인했습니다. 운영 DB에
쓰기를 발생시키는 실제 OpenAI Chat·재시작 영속성 검증은 위 2026-08-29 증빙을 최종
기준으로 유지하여 자동 검증과 운영 검증의 범위를 구분합니다. 성공한 Chat 요청
`0947aa18-f5dc-423f-b6f0-aa2e6371f90c`에서 아래 이벤트가 동일한 `request_id`를
공유하는 것을 확인했습니다. 질문·응답 본문과 Secret은 로그에 기록되지 않습니다.

```text
request_received
ai_call_started
ai_call_succeeded
db_save_succeeded
request_completed
```

Railway Container 재시작 후 Health 요청
`9988c3aa-43db-47e1-8d31-c8c406b2cc9e`가 `200`으로 완료됐고, Frontend를
새로고침해도 재시작 전 Chat과 AI 응답이 그대로 조회되어 `/data` Volume의 SQLite
영속성을 재확인했습니다.

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

### 주요 PR과 Git 기여 증빙

| 팀원 | 대표 작업 및 PR |
|---|---|
| 박주영 | [Backend PR #4 로그인 기본 작업](https://github.com/bangahee/ChatFlow-backend/pull/4), [Backend PR #11 Swagger·OpenAPI 검증](https://github.com/bangahee/ChatFlow-backend/pull/11) |
| 김승우 | [Backend PR #5 DB·Chat API](https://github.com/bangahee/ChatFlow-backend/pull/5), [Frontend PR #3 React Frontend 통합](https://github.com/bangahee/ChatFlow/pull/3) |
| 반가희 | [Backend PR #6 OpenAI·안정성](https://github.com/bangahee/ChatFlow-backend/pull/6), [Backend PR #7 운영 로그·통합 검증](https://github.com/bangahee/ChatFlow-backend/pull/7), [Frontend PR #7 역할·기여 정합성](https://github.com/bangahee/ChatFlow/pull/7) |
| 김두운 | [Frontend PR #3 React Frontend 통합](https://github.com/bangahee/ChatFlow/pull/3), [Frontend PR #23 말풍선 줄바꿈](https://github.com/bangahee/ChatFlow/pull/23) 및 UI·UX·반응형·사용성 커밋 |
| 평가·운영 보완 | [Backend PR #26 평가 요구사항·운영 감사](https://github.com/bangahee/ChatFlow-backend/pull/26), [Backend PR #29 최종 평가 증빙 정합성](https://github.com/bangahee/ChatFlow-backend/pull/29), [Frontend PR #25 입력 상태 회귀 수정](https://github.com/bangahee/ChatFlow/pull/25) |
| 최종 Release | [Backend PR #28 develop→main](https://github.com/bangahee/ChatFlow-backend/pull/28), [Frontend main `bd67bc4`](https://github.com/bangahee/ChatFlow/commit/bd67bc43293c9271ffa8c760011bc330ca01018d) |

README 설명과 실제 구현·이력을 대조할 때는 다음 연결표를 사용합니다.

| 평가 영역 | Source 및 검증 | 대표 PR |
|---|---|---|
| 인증·접근 제어 | [`dependencies.py`](app/dependencies.py), [`auth.py`](app/routers/auth.py), [`test_auth_api.py`](tests/test_auth_api.py) | [PR #4](https://github.com/bangahee/ChatFlow-backend/pull/4), [PR #21](https://github.com/bangahee/ChatFlow-backend/pull/21) |
| DB·Chat·Repository | [`models.py`](app/models.py), [`repositories/`](app/repositories), [`test_chat_service.py`](tests/test_chat_service.py) | [PR #5](https://github.com/bangahee/ChatFlow-backend/pull/5), [PR #26](https://github.com/bangahee/ChatFlow-backend/pull/26) |
| OpenAI·오류·운영 로그 | [`ai.py`](app/services/ai.py), [`observability.py`](app/observability.py), [`test_observability.py`](tests/test_observability.py) | [PR #6](https://github.com/bangahee/ChatFlow-backend/pull/6), [PR #7](https://github.com/bangahee/ChatFlow-backend/pull/7), [PR #26](https://github.com/bangahee/ChatFlow-backend/pull/26) |
| 사용자·관리자 UI | [Frontend `src/pages`](https://github.com/bangahee/ChatFlow/tree/main/src/pages), [Frontend 테스트](https://github.com/bangahee/ChatFlow/blob/main/src/App.test.tsx) | [Frontend PR #3](https://github.com/bangahee/ChatFlow/pull/3), [Frontend PR #24](https://github.com/bangahee/ChatFlow/pull/24), [Frontend PR #25](https://github.com/bangahee/ChatFlow/pull/25) |
| 최종 브랜치 이력 | Backend `develop → main`, Frontend 최신 `main` | [Backend PR #28](https://github.com/bangahee/ChatFlow-backend/pull/28), [Frontend PR #25](https://github.com/bangahee/ChatFlow/pull/25) |

표준 흐름은 기능 Branch → Pull Request → 다른 팀원 Review → `develop` Merge →
`develop → main` Release PR입니다. Backend는 이 흐름으로 PR #28까지 Release했습니다.
Release 이후의 제출 직전 문서·평가 호환성 수정은 여러 PR로 분산하지 않고 Review와
필수 CI를 거친 단일 Stabilization PR로 `main`에 반영할 수 있습니다. Frontend의 UI
긴급 수정 PR #23·#24·#25도 CI 확인 후 `main`에 직접 병합한 예외입니다. 이런 예외 이후 추가
개발이 필요하면 `main → develop` 동기화 PR을 먼저 만들고, 기능 Branch를 `main`에
직접 병합하는 방식을 일반 개발 흐름으로 반복하지 않습니다.

세부 Commit은 각 PR의 Commits 탭에서 작성자별로 확인할 수 있으며, 자동 생성된 Merge
Commit을 제외한 유의미한 작업 Commit을 개인별 기여 기준으로 사용합니다. README의
구현 설명은 위 PR 링크와 각 Source 링크를 통해 실제 이력과 대조할 수 있습니다.
