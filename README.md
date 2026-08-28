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

## 주요 기능

- Argon2 비밀번호 해시와 JWT Bearer 인증
- 사용자별 Chat 기록 저장·조회·삭제
- 관리자 전용 일반 사용자 목록 및 사용자별 전체 대화 조회(조회 전용)
- 최근 대화 최대 3개를 과거→최신 순서로 OpenAI에 전달
- OpenAI timeout, rate limit, 연결 오류와 5xx 재시도
- 오류 유형별 502, 503, 504 응답과 실패 응답 미저장
- 요청 수신부터 AI 호출과 DB 저장, 요청 완료까지 동일 `request_id` 추적
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

일반 사용자의 기록 조회·추적은 인증된 `GET /api/me/chats`와 Frontend의 내 대화
기록 화면으로 제한됩니다. 별도 관리자 권한을 가진 계정은 채팅 API를 사용할 수
없고, 관리자 API를 통해 일반 사용자와 선택 사용자의 대화 기록만 조회할 수 있습니다.

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

SQLite와 SQLAlchemy 2.0을 사용하며 `User : ChatLog = 1:N` 관계입니다.

```text
users                         chat_logs
├── id PK                 ┌── id PK
├── username UNIQUE       ├── user_id FK → users.id
├── hashed_password       ├── question
├── is_admin              ├── response
└── created_at            └── created_at
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

- DB 저장 성공·실패 구현: [app/services/chat.py](https://github.com/bangahee/ChatFlow-backend/blob/main/app/services/chat.py)
- DB 저장 실패와 rollback 검증: [tests/test_chat_service.py](https://github.com/bangahee/ChatFlow-backend/blob/main/tests/test_chat_service.py)
- 요청·인증 로그 검증: [tests/test_observability.py](https://github.com/bangahee/ChatFlow-backend/blob/main/tests/test_observability.py)

## 테스트와 CI

테스트는 각 실행마다 임시 SQLite 파일과 Mock OpenAI Client를 사용하므로 운영
DB, 실제 API Key 또는 실제 backoff 대기가 필요하지 않습니다.

```bash
python -m pytest -q
```

현재 구현 기준 결과는 `121 passed`입니다.

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

### 2026-08-28 Production 통합 검증

| 항목 | 결과 |
|---|---|
| Railway Health | `GET /health` → `200 {"status":"ok"}` |
| Vercel Frontend | `main` 커밋 `6d877da`, Production `Ready` |
| CORS | Vercel Origin의 Login Preflight `200` 및 허용 Origin Header 확인 |
| 사용자 흐름 | 회원가입 `201` → 로그인 `200` → 실제 OpenAI Chat `201` → 기록 조회 성공 |
| 인증 복원 | Frontend 새로고침 후 로그인 상태와 기록 유지 |
| SQLite 영속성 | Railway Container 재시작 전·후 동일 사용자와 대화 수 `1` 유지 |
| Frontend 오류 | 검증 중 Browser Console Error 없음 |

영속성 검증 당시 Railway는 `main` 커밋 `f82fc97`을 실행했습니다. 운영 INFO 로그
출력 보완은 PR #17을 통해 `develop` 커밋 `eb25497`에 반영됐으며, 최종 Release
PR #13을 `main`에 병합하고 Railway를 재배포한 뒤 로그 이벤트를 다시 확인합니다.

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
| 김두운 | [Frontend PR #3 React Frontend 통합](https://github.com/bangahee/ChatFlow/pull/3) 및 해당 PR의 UI·UX·반응형·사용성 커밋 |

두 저장소 모두 기능 Branch → Pull Request → 다른 팀원 Review → `develop`
Merge → `develop → main` Release PR 흐름을 사용합니다. 세부 Commit은 각 PR의
Commits 탭에서 작성자별로 확인할 수 있으며, 자동 생성된 Merge Commit을 제외한
유의미한 작업 Commit을 개인별 기여 기준으로 사용합니다.
