# ChatFlow 프로젝트 설명·평가 A–Z 가이드

> 기준일: 2026-09-02  
> Backend: [ChatFlow-backend](https://github.com/bangahee/ChatFlow-backend)  
> Frontend: [ChatFlow](https://github.com/bangahee/ChatFlow)  
> 서비스: [Frontend](https://chat-flow-topaz.vercel.app) · [Backend Health](https://chatflow-backend-production-b90c.up.railway.app/health)

이 문서는 `docs/subject7-1.md`의 과제 요구사항과 31개 평가항목을 기준으로,
ChatFlow를 처음부터 끝까지 설명하고 직접 실행·시연할 수 있도록 만든 발표 및
질의응답용 참고서다. 단순히 “구현했다”라고 답하는 대신 **왜 이 구조를 선택했고,
요청이 코드 안에서 어떻게 흐르며, 실패했을 때 어떻게 안전하게 처리되는지**까지
설명하는 것을 목표로 한다.

---

## 0. 가장 먼저 외울 프로젝트 설명

### 30초 설명

ChatFlow는 로그인한 사용자가 웹에서 질문을 보내면 FastAPI 서버가 최근 대화 최대
3개를 문맥으로 구성해 OpenAI Responses API를 호출하고, 성공한 질문과 답변을
사용자별 SQLite DB에 저장하는 AI 챗봇 서비스다. React Frontend는 Vercel에,
FastAPI Backend는 Railway에 분리 배포했으며 JWT 인증, 입력 검증, 관리자 조회,
AI timeout·retry, 구조화 운영 로그, CI와 SQLite Volume 영속성을 포함한다.

### 문제 정의

단순히 브라우저에서 OpenAI를 직접 호출하면 API Key가 노출되고, 사용자별 기록·문맥·
접근 권한을 관리하기 어렵다. 또한 AI 장애나 DB 오류가 발생했을 때 어떤 요청이
실패했는지 추적하기 어렵다. ChatFlow는 다음 문제를 하나의 서비스 흐름으로 해결한다.

- OpenAI Key를 서버에만 보관해 Client 노출을 방지한다.
- 인증된 사용자별로 질문과 응답을 분리해 저장한다.
- 최근 대화를 다음 AI 요청의 문맥으로 전달한다.
- timeout, 재시도, 오류 상태 코드와 사용자 메시지를 제공한다.
- `request_id`로 HTTP 요청, AI 호출, DB 저장 결과를 연결한다.

### 핵심 사용자 흐름

```text
회원가입
  → 로그인 및 JWT 발급
  → 질문 입력
  → Backend 인증·입력 검증
  → 최근 대화 3개 조회
  → OpenAI Responses API 호출
  → 질문·응답 DB 저장
  → Frontend에 응답 표시
  → 내 기록 조회·삭제
```

### 관리자 흐름

```text
일반 회원가입
  → Railway 운영 Shell에서 관리자 권한 부여
  → 관리자 로그인
  → 일반 사용자 목록·대화 수 조회
  → 선택 사용자의 전체 대화 기록 조회
```

관리자는 운영 조회 전용이므로 일반 Chat API를 사용할 수 없다.

---

## 1. 전체 아키텍처

```text
사용자 Browser
    │
    │ React UI / HTTPS
    ▼
Vercel Frontend
    │
    │ JSON REST API
    │ Authorization: Bearer <JWT>
    ▼
Railway FastAPI Backend
    ├── CORS / Request logging middleware
    ├── Auth Router → Auth Service → User Repository
    ├── Chat Router → Chat Service → Chat Repository
    │                         ├── SQLite /data/chatflow.db
    │                         └── OpenAI Responses API
    ├── Admin Router → Admin Service → Repository
    └── Health Router

운영 추적
    ├── Railway 한 줄 JSON Application Log
    └── request_logs Table
```

### 계층별 책임

| 계층 | 책임 | 대표 파일 |
|---|---|---|
| Frontend Page/Component | 화면, 입력, 로딩·오류 UX | Frontend `src/pages`, `src/components` |
| API Client | Backend URL, Bearer Header, 오류 변환 | Frontend `src/api/client.ts` |
| Router | HTTP Method·Path·Status·Schema 계약 | `app/routers/` |
| Dependency | DB Session·현재 사용자·권한·AI 주입 | `app/dependencies.py` |
| Service | 인증, AI 호출, Transaction 등 업무 규칙 | `app/services/` |
| Repository | SQLAlchemy Query와 영속성 연산 | `app/repositories/` |
| Schema | Pydantic 요청·응답 검증 | `app/schemas/` |
| Model | SQLAlchemy Table Mapping | `app/models.py` |
| Config | 환경 변수 읽기와 형식 검증 | `app/config.py` |
| Observability | `request_id`, 구조화 로그, 감사 DB 기록 | `app/observability.py` |

### 왜 Frontend와 Backend를 분리했는가?

- React와 FastAPI의 배포·빌드 주기를 독립적으로 관리할 수 있다.
- Backend는 JSON API 계약에 집중하고 Frontend는 UI/UX에 집중한다.
- OpenAI Key와 DB는 Backend에만 존재하므로 Client Bundle에 포함되지 않는다.
- 단점은 Origin이 달라 CORS 설정이 필요하다는 점이며, Railway의
  `CORS_ORIGINS`에 실제 Vercel Origin을 허용해 해결한다.

---

## 2. 저장소 구조를 설명하는 법

### Backend

```text
app/
├── main.py                  앱 생성, Middleware, Router 등록
├── config.py                환경 변수 Settings
├── database.py              Engine, Session, Schema 생성
├── dependencies.py          인증·권한·DB·AI 의존성
├── models.py                users, chat_logs, request_logs
├── observability.py         요청·인증·감사 로그
├── routers/
│   ├── auth.py              회원가입, 로그인, 내 정보
│   ├── chat.py              질문, 내 기록 조회·삭제
│   ├── admin.py             관리자 조회
│   └── health.py            배포 상태 확인
├── schemas/                 Pydantic 요청·응답 모델
├── repositories/            DB Query와 Repository Protocol
└── services/
    ├── auth.py              Argon2, JWT
    ├── chat.py              AI→DB 저장 Transaction
    ├── ai.py                OpenAI, context, timeout/retry
    └── admin.py             관리자 조회 업무 흐름

scripts/
├── check_logs.sql           대화·요청 로그 조회
└── grant_admin.py           기존 사용자 관리자 승격

tests/                       단위·API·통합·OpenAPI 테스트
.github/workflows/test.yml   Backend pytest CI
railway.json                 Railway 실행·Health 설정
```

### Frontend

```text
src/
├── App.tsx                  React Route 구성
├── api/                     API Client와 Type
├── auth/                    JWT 상태·Route Guard
├── pages/
│   ├── RegisterPage.tsx     회원가입
│   ├── LoginPage.tsx        로그인
│   ├── ChatPage.tsx         질문·답변·기록
│   └── AdminPage.tsx        관리자 조회
├── components/              공통 UI, Markdown, 오류 경계
├── hooks/                   Scroll 등 재사용 Hook
└── utils/                   입력 검증·날짜 처리

.github/workflows/quality.yml  lint·test·build CI
vercel.json                    SPA Route Rewrite
```

---

## 3. 처음부터 실행하는 방법

### 3.1 Backend 로컬 실행

필요 조건은 Python 3.13과 OpenAI API Key다.

```bash
git clone https://github.com/bangahee/ChatFlow-backend.git
cd ChatFlow-backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

`.env`에서 최소한 다음 값을 설정한다.

```dotenv
APP_ENV=development
LOG_LEVEL=INFO
SECRET_KEY=32자-이상의-충분히-긴-임의-문자열
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./chatflow.db
OPENAI_API_KEY=실제-OpenAI-Key
OPENAI_MODEL=gpt-5-nano
OPENAI_TIMEOUT_SECONDS=20
OPENAI_MAX_RETRIES=3
CORS_ORIGINS=http://localhost:5173
```

실행:

```bash
uvicorn app.main:app --reload
```

확인 주소:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health: `http://localhost:8000/health`

### 3.2 Frontend 로컬 실행

```bash
git clone https://github.com/bangahee/ChatFlow.git
cd ChatFlow
npm install
cp .env.example .env
npm run dev
```

Frontend `.env`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

접속 주소는 기본적으로 `http://localhost:5173`이다.

### 3.3 테스트

Backend:

```bash
python -m pytest -q
```

최신 검증 결과는 `124 passed`다. 테스트는 임시 SQLite DB와 Mock OpenAI Client를
사용하므로 실제 OpenAI Key나 실제 대기 시간이 필요하지 않다.

Frontend:

```bash
npm run lint -- --max-warnings=0
npm test
npm run build
```

최신 검증 결과는 Frontend 테스트 `31 passed`, lint와 Production build 통과다.

### 3.4 Production 주소

- Frontend: `https://chat-flow-topaz.vercel.app`
- Backend: `https://chatflow-backend-production-b90c.up.railway.app`
- Health: `https://chatflow-backend-production-b90c.up.railway.app/health`

---

## 4. API를 직접 시연하는 방법

아래 `<backend>`에는 로컬이면 `http://localhost:8000`, Production이면 Railway
Backend URL을 넣는다.

### 4.1 Health

```bash
curl -i <backend>/health
```

기대 결과:

```json
{"status":"ok"}
```

### 4.2 회원가입

```bash
curl -X POST <backend>/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"chat_user","password":"password123"}'
```

회원가입은 `201`이고 평문 비밀번호를 응답하지 않는다.

### 4.3 로그인

```bash
curl -X POST <backend>/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"chat_user","password":"password123"}'
```

응답의 `access_token`을 이후 `<jwt>`로 사용한다.

### 4.4 현재 사용자

```bash
curl <backend>/api/me \
  -H 'Authorization: Bearer <jwt>'
```

### 4.5 질문 전송

```bash
curl -X POST <backend>/api/chat \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <jwt>' \
  -d '{"question":"FastAPI의 장점을 설명해 줘"}'
```

성공은 `201`이며 질문, AI 응답, 생성 시각, `request_id`가 반환된다.

### 4.6 내 기록 조회

```bash
curl <backend>/api/me/chats \
  -H 'Authorization: Bearer <jwt>'
```

### 4.7 내 기록 전체 삭제

```bash
curl -X DELETE <backend>/api/me/chats \
  -H 'Authorization: Bearer <jwt>'
```

### 4.8 비로그인 제한 확인

```bash
curl -i <backend>/api/me/chats
```

기대 결과는 `401`과 다음 응답이다.

```json
{"detail":"로그인이 필요합니다."}
```

---

## 5. 인증과 보안을 A–Z로 설명하기

### 회원가입

1. `RegisterRequest`가 username과 password를 검증한다.
2. Service가 중복 username을 조회한다.
3. `pwdlib`의 권장 Argon2 설정으로 비밀번호를 Hash한다.
4. Repository가 `User`를 Session에 추가한다.
5. Service가 commit하고 사용자 정보를 반환한다.
6. DB에는 평문 비밀번호가 아니라 `hashed_password`만 저장된다.

### 입력 규칙

| 입력 | Backend 규칙 | Frontend 규칙 |
|---|---|---|
| username | 3~50자, 영문·숫자·`_` | 동일 |
| password | 8~128자 | 동일 + 회원가입 확인 입력 |
| question | Trim 후 1~500자 | 동일, 남은 글자 표시·전송 차단 |

Pydantic 모델은 `extra="forbid"`를 사용해 예상하지 않은 필드도 거부한다.

### JWT란?

JWT는 서버가 서명한 인증 Token이다. 이 프로젝트의 Payload에는 다음 값이 있다.

- `sub`: username
- `iat`: 발급 시각
- `exp`: 만료 시각

서버는 `SECRET_KEY`와 `HS256`으로 서명하고, 보호 API 요청마다 Token의 서명·만료·
필수 Claim을 확인한 후 DB에서 현재 사용자를 다시 조회한다.

### 왜 SessionMiddleware를 사용하지 않았는가?

과제는 인증 상태 구현을 요구하지만 반드시 Cookie Session만 사용하라고 제한하지
않는다. 이 프로젝트는 Stateless JWT Bearer 방식을 선택했다.

- Frontend가 Token을 저장한다.
- 요청마다 `Authorization: Bearer <token>`을 보낸다.
- 새로고침 시 `/api/me`로 사용자와 Token 만료 여부를 복원한다.
- 서버 Instance가 여러 개여도 공용 Session Store가 필요하지 않다.

따라서 `SessionMiddleware` 대신 FastAPI `Depends(get_current_user)`를 재사용한다.
`get_current_admin`과 `get_current_chat_user`는 이를 확장해 역할까지 제한한다.

### 주의할 보안 Trade-off

Frontend는 현재 JWT를 `localStorage`에 저장한다. 새로고침 복원이 쉽지만 XSS가
발생하면 Token 탈취 위험이 있으므로, Markdown에서 Raw HTML을 실행하지 않고 React의
기본 Escape와 Error Boundary를 사용한다. 더 높은 보안 수준이 필요하면 짧은 Access
Token과 `HttpOnly`, `Secure`, `SameSite` Cookie 기반 Refresh Token 구조를 고려한다.

### CORS란?

Browser는 Origin이 다른 Frontend가 Backend에 요청할 때 CORS 정책을 확인한다.
Backend는 `CORSMiddleware`에서 허용 Origin만 열고, Bearer Token 방식이므로 Cookie
Credential이 필요 없어 `allow_credentials=False`를 사용한다. Production 허용값은
정확히 다음과 같다.

```text
https://chat-flow-topaz.vercel.app
```

### 비로그인 요청을 제한하는 이유

질문과 답변은 사용자별 개인 데이터이며 이전 기록은 다음 AI 문맥으로 사용된다.
인증 없이 허용하면 기록 소유자를 확인할 수 없어 다른 사용자의 대화가 노출되거나
잘못된 문맥이 전달될 수 있다.

---

## 6. Chat 요청 내부 흐름

```text
POST /api/chat
  → Request logging middleware가 request_id 생성
  → HTTPBearer가 Bearer Token 추출
  → JWT 검증 및 User 조회
  → 관리자가 아닌지 확인
  → ChatRequest가 질문 Trim·길이 검증
  → Repository가 해당 사용자의 최근 3개 Chat 조회
  → AIService가 Context 구성 및 OpenAI 호출
  → AI 성공 시에만 ChatLog 추가
  → commit·refresh
  → ChatResponse 201
  → request_logs 저장 및 request_completed 기록
```

AI 호출이 실패하면 ChatLog를 만들기 전에 예외가 발생하므로 실패한 질문·가짜 응답이
대화 기록에 남지 않는다. DB 저장이 실패하면 `rollback()`해 부분 저장을 막는다.

### Context 구성 순서

```text
1. system: ChatFlow의 역할과 안전한 답변 지침
2. 과거 user 질문 1
3. 과거 assistant 응답 1
4. 과거 user 질문 2
5. 과거 assistant 응답 2
6. 과거 user 질문 3
7. 과거 assistant 응답 3
8. 현재 user 질문
```

최근 3개만 사용하는 이유는 대화 연속성을 제공하면서 Token 사용량, 비용, 지연과
불필요한 개인정보 전송을 제한하기 위해서다. DB Query는 최신 3개를 고른 후 과거→
최신 순으로 뒤집어 자연스러운 문맥 순서를 보장한다.

---

## 7. OpenAI 연동과 장애 대응

### 기본 호출

- 공식 `AsyncOpenAI` Client 사용
- Responses API 사용
- Model: `gpt-5-nano`
- `store=False`: OpenAI 측 응답 저장을 요청하지 않음
- `response.output_text`를 Trim해 반환
- SDK 자동 재시도는 `max_retries=0`으로 끄고 앱 정책으로 통제

### Timeout과 Retry

`OPENAI_MAX_RETRIES=3`은 최초 1회 + 추가 3회, 총 4회를 의미한다. 각 시도에는
`OPENAI_TIMEOUT_SECONDS=20`의 hard timeout이 적용되며 추가 시도 전 대기 시간은
`1초 → 2초 → 4초`다.

| 실패 | 재시도 | 최종 HTTP | 사용자 메시지 |
|---|---:|---:|---|
| Timeout | O | 504 | AI 응답 시간이 초과되었습니다. |
| 일반 Rate Limit | O | 503 | AI 서비스를 일시적으로 사용할 수 없습니다. |
| Connection Error | O | 502 | AI 서비스 응답 처리 중 오류가 발생했습니다. |
| OpenAI 5xx | O | 503 | AI 서비스를 일시적으로 사용할 수 없습니다. |
| Quota/Billing 429 | X | 503 | AI 서비스를 일시적으로 사용할 수 없습니다. |
| 인증·권한·잘못된 요청 4xx | X | 502 | AI 서비스 응답 처리 중 오류가 발생했습니다. |
| 빈 응답·잘못된 응답 | X | 502 | AI 서비스 응답 처리 중 오류가 발생했습니다. |

Quota 오류를 재시도하지 않는 이유는 잔액이나 사용 한도 문제가 시간이 조금 지난다고
즉시 해결되지 않기 때문이다. 반면 일시적 연결·서버 오류는 재시도로 회복될 수 있다.

### 왜 비동기 호출인가?

OpenAI 응답을 기다리는 작업은 CPU 계산이 아니라 Network I/O다. `async/await`를
사용하면 대기 중 Event Loop가 다른 요청을 처리할 수 있어 서버 자원을 효율적으로
사용한다.

---

## 8. Database와 Transaction

### ERD

```text
users 1 ─────────── N chat_logs
  │                     │
  └── 1 ─ N request_logs┘

users
├── id PK
├── username UNIQUE
├── hashed_password
├── is_admin
└── created_at

chat_logs
├── id PK
├── user_id FK → users.id
├── question
├── response
└── created_at

request_logs
├── id PK
├── request_id UNIQUE
├── user_id FK → users.id, nullable
├── chat_id FK → chat_logs.id, nullable
├── method / path / status_code / latency_ms
├── origin / content_type / user_agent
├── error_type
└── created_at
```

평가항목에서 `conversations`라고 부르는 데이터는 이 프로젝트의 `chat_logs`다.
`chat_logs` 한 Row가 한 번의 질문과 응답을 나타낸다.

### Repository와 Service를 나눈 이유

- Repository: “어떤 SQL Query를 실행할 것인가?”
- Service: “어떤 업무 순서와 Transaction으로 실행할 것인가?”
- Router: “어떤 HTTP 계약으로 노출할 것인가?”

분리하면 Query는 Mock Repository로 대체할 수 있고, Service는 HTTP와 무관하게 단위
테스트할 수 있다. `ChatRepository` Protocol은 Service가 필요한 연산을 구조적으로
정의해 구현 교체와 테스트 Double 주입을 쉽게 한다.

### Commit과 Rollback

- AI 성공 후 `add_chat()` → `commit()` → `refresh()` 순서로 저장한다.
- 저장 중 예외가 발생하면 `rollback()`한다.
- 조회·삭제 오류도 Session 상태를 정리한다.
- SQLite 연결마다 `PRAGMA foreign_keys=ON`을 적용한다.

### Schema 생성과 Migration

서버 시작 시 `create_all()`로 빈 DB의 Table을 만든다. 하지만 `create_all()`은 기존
Column 변경을 자동으로 수행하는 Migration Tool이 아니다. 현재는 Legacy DB에
`is_admin` Column이 없을 때 한 번 추가하는 호환 Upgrade만 코드로 제공한다.

향후 Schema 변경 절차:

1. `/data/chatflow.db` Backup
2. Versioned SQL 또는 Alembic Migration 작성
3. 운영 DB 사본에서 Migration + 전체 테스트
4. 쓰기 중지 후 운영 DB에 한 번 적용
5. Health·로그인·Chat·기존 기록 확인
6. 실패 시 Backup 복원과 이전 Release Rollback

Backup 예시:

```bash
sqlite3 /data/chatflow.db ".backup '/data/chatflow-backup-YYYYMMDD-HHMM.db'"
```

### SQL 로그 조회

로컬:

```bash
sqlite3 -header -column ./chatflow.db < scripts/check_logs.sql
```

Railway Service Shell:

```bash
sqlite3 -header -column /data/chatflow.db < scripts/check_logs.sql
```

이 Script는 최근 100개 Chat을 사용자·요청 감사 정보와 함께 최신순으로 조회한다.

---

## 9. 운영 로그와 `request_id`

### 이벤트 순서

```text
request_received
  ├── auth_failed
  ├── ai_call_started
  ├── ai_call_succeeded 또는 ai_call_failed
  ├── db_save_succeeded 또는 db_save_failed
  └── request_completed
```

모든 이벤트는 같은 `request_id`를 공유한다. 응답 Header의 `X-Request-ID`와 Chat
응답 Body의 `request_id`도 같아 사용자가 제보한 실패를 Railway Log에서 바로 찾을
수 있다.

### 기록하는 정보

- Method, Path, Status Code
- 전체 응답 시간 `latency_ms`
- AI attempt, AI latency
- 질문·응답 **길이**
- 오류 Type
- Allow-list Header: Origin, Content-Type, User-Agent
- 인증 성공 후 user_id, Chat 성공 후 chat_id

### 기록하지 않는 정보

- `Authorization` Header와 JWT
- Cookie
- 비밀번호
- OpenAI API Key와 `SECRET_KEY`
- 질문·응답 본문

질문과 응답 원문은 접근 제어가 있는 `chat_logs`에만 저장하고 Application Log에는
복제하지 않는다. `/health`는 DB나 OpenAI에 의존하지 않으며 `request_logs`에서도
제외해 Health Probe가 감사 DB를 불필요하게 증가시키지 않게 한다.

---

## 10. 관리자 계정 생성과 사용

일반 회원가입만으로는 관리자 권한을 받을 수 없고, 권한 변경 HTTP API도 제공하지
않는다. 공개 API로 관리자 승격을 제공하면 공격자가 권한을 얻을 위험이 있기 때문이다.

1. Frontend에서 관리자 전용 사용자를 먼저 회원가입한다.
2. Railway `ChatFlow-backend → Console`에 들어간다.
3. 같은 운영 DB 환경에서 다음 명령을 실행한다.

```bash
python -m scripts.grant_admin <username>
```

예:

```bash
python -m scripts.grant_admin admin_1
```

4. 로그아웃 후 해당 계정으로 다시 로그인한다.
5. `/api/me`의 `is_admin`이 `true`이고 `/admin` 화면이 열리는지 확인한다.

이 명령은 같은 사용자에게 다시 실행해도 안전한 Idempotent 작업이다. 관리자는 일반
사용자 목록과 사용자별 Chat만 읽을 수 있고, 관리자 계정 자체는 목록에서 제외된다.
관리자가 `/api/chat` 또는 `/api/me/chats`를 사용하면 의도적으로 `403`을 반환한다.

---

## 11. 배포 설정을 설명하는 법

### Railway Backend

`railway.json`:

- Builder: Railpack
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Path: `/health`
- Health timeout: 100초
- Restart: `ON_FAILURE`

Production 환경 변수:

```dotenv
APP_ENV=production
LOG_LEVEL=INFO
SECRET_KEY=<서버 전용 긴 임의값>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:////data/chatflow.db
OPENAI_API_KEY=<서버 전용 Key>
OPENAI_MODEL=gpt-5-nano
OPENAI_TIMEOUT_SECONDS=20
OPENAI_MAX_RETRIES=3
CORS_ORIGINS=https://chat-flow-topaz.vercel.app
```

Railway Volume `chatflow-backend-volume`을 Backend의 `/data`에 Mount한다. 현재
Volume Size는 500MB이며 DB 파일은 `/data/chatflow.db`다. 컨테이너 파일시스템은
재배포 때 사라질 수 있지만 Volume 데이터는 유지된다.

### Vercel Frontend

```dotenv
VITE_API_BASE_URL=https://chatflow-backend-production-b90c.up.railway.app
```

현재 이 변수는 Production과 Preview에 적용된다. `VITE_` Prefix 변수는 Build 시
Browser Bundle에 포함되므로 **비밀값을 넣으면 안 된다**. Backend 공개 URL은 공개돼도
되는 값이다. `OPENAI_API_KEY`, `SECRET_KEY`는 Vercel에 등록하지 않는다.

`vercel.json`의 Rewrite는 `/chat`, `/admin` 같은 Client Route를 새로고침해도
`index.html`을 반환해 React Router가 처리하도록 한다.

### 배포 후 필수 확인

1. Railway Deployment가 `ACTIVE`인지 확인
2. `/health`가 `200 {"status":"ok"}`인지 확인
3. Vercel Login Page가 외부 네트워크에서 열리는지 확인
4. Vercel Origin의 CORS Preflight가 `200`인지 확인
5. 회원가입 → 로그인 → 실제 Chat → 기록 조회
6. Railway 재시작 후 같은 계정과 기록이 유지되는지 확인
7. Railway Log에서 같은 `request_id`의 이벤트 확인

---

## 12. Git·PR·CI 전략

이 프로젝트는 간소화된 Git Flow를 사용한다.

```text
feature/fix/docs branch
  → Pull Request
  → CI
  → Review
  → develop
  → develop에서 통합 검증
  → Release PR
  → main
  → 배포
```

### Branch 역할

- `main`: 제출·Production Release 기준
- `develop`: 다음 Release 통합 기준
- 기능 Branch: 한 기능 또는 수정 단위

### CI

- Backend: Python 3.13, dependency 설치, `python -m pytest -q`
- Frontend: Node 24, `npm ci`, lint, test, build
- 두 저장소 모두 `develop`, `main` Push와 대상 PR에서 실행
- Backend 테스트는 Mock OpenAI를 사용하므로 Production Secret이 필요 없음

### 팀 역할

| 담당자 | 주요 영역 |
|---|---|
| 박주영 | FastAPI 기반, Settings, CORS, Schema, 인증·JWT |
| 김승우 | SQLAlchemy Model·Repository, Chat Service/API, DB 테스트 |
| 반가희 | OpenAI, timeout/retry, 운영 로그, Health, CI, Railway, 최종 통합 |
| 김두운 | Frontend UI/UX, 반응형, 사용자 흐름 보완 |

대표 구현·PR 링크는 [Backend README의 기여 증빙](../README.md#주요-pr과-git-기여-증빙)에서
확인한다. 평가 제출 전에는 GitHub Commits/Contributors에서 Merge Commit을 제외한
팀원별 유의미한 Commit 10회 이상을 마지막으로 확인한다.

---

# 13. 평가항목 31개 모범 답변

아래 각 항목은 발표 때 그대로 답할 수 있도록 **요구 의미 → 프로젝트 답변 → 근거 →
시연** 순서로 정리했다.

## 항목 1 — README 프로젝트 목적과 핵심 흐름

**답변:** README 첫 부분에 단순 AI 호출의 한계인 인증, 문맥, 기록 보관, 장애 추적
문제를 정의하고 대상 사용자를 설명한다. 핵심 흐름은 회원가입 → 로그인 → 질문 → 최근
3개 문맥을 포함한 AI 응답 → DB 저장 → 기록 조회·삭제다.

- 근거: `README.md`의 “문제, 대상 사용자, 핵심 시나리오”
- 시연: Frontend에서 실제로 위 순서를 한 번 수행한다.
- 핵심 개념: 기능 나열이 아니라 어떤 문제를 왜 해결했는지 설명해야 한다.

## 항목 2 — 파일 수준 구조와 아키텍처

**답변:** README에 Vercel React → Railway FastAPI → OpenAI/SQLite 관계도가 있고,
`app/main.py`, Router, Schema, Repository, Service, Model의 책임을 파일 수준으로
설명한다. `main.py`는 앱 Factory, Middleware, Router 등록과 lifespan을 담당한다.

- 근거: `README.md` “시스템 구성”, `app/main.py`
- 시연: Swagger와 Repository Tree를 함께 보여준다.
- 핵심 개념: 관심사 분리와 의존 방향을 설명한다.

## 항목 3 — API 요청·응답과 성공·실패 JSON

**답변:** README에 전체 Endpoint 표, curl 요청, 회원가입·로그인·Chat·기록 성공 JSON,
401·422·502 등 실패 JSON과 상태별 의미가 있다. Router의 `responses`에도 오류 Schema가
등록돼 Swagger Response Table에서 확인할 수 있다.

- 근거: `app/routers/*.py`, `app/schemas/common.py`, `tests/test_openapi.py`
- 시연: `/docs`에서 Endpoint 하나를 열고 201/401/422/502 응답을 확인한다.
- 핵심 개념: HTTP Status와 JSON Body를 함께 API 계약으로 본다.

## 항목 4 — conversations 필드와 ERD

**답변:** 평가에서 말하는 conversations는 이 프로젝트의 `chat_logs`에 해당한다.
README에는 users, chat_logs, request_logs의 필드·제약과 관계도가 있다.

- 근거: `app/models.py`, README “Database”
- 시연: ERD와 실제 SQLite `.schema` 또는 Swagger 응답을 비교한다.
- 핵심 개념: Table 이름이 달라도 사용자·질문·응답·시각 추적 의미가 충족되는지가 중요하다.

## 항목 5 — `scripts/check_logs.sql`

**답변:** 로컬과 Railway Volume DB 각각의 실행 명령이 README와 SQL 주석에 있다.

```bash
sqlite3 -header -column ./chatflow.db < scripts/check_logs.sql
sqlite3 -header -column /data/chatflow.db < scripts/check_logs.sql
```

- 근거: `scripts/check_logs.sql`
- 시연: 최근 Chat 100개의 사용자·질문·응답·request_id·상태·latency를 조회한다.
- 핵심 개념: 평가자가 DB 저장 결과를 독립적으로 검증할 수 있어야 한다.

## 항목 6 — 구성원 역할

**답변:** README에 Backend A/B/C 역할과 Frontend 담당, 대표 PR·Source 연결표가 있다.
역할 설명은 실제 Git 이력과 대조 가능하다.

- 근거: README “브랜치 전략과 역할”, “주요 PR과 Git 기여 증빙”
- 시연: 팀원 한 명의 대표 PR과 Commit 탭을 연다.
- 핵심 개념: 문서상의 역할과 실제 기여가 모순되면 안 된다.

## 항목 7 — 회원가입 UI와 서버 처리 흐름

**답변:** `RegisterPage`에 username, password, password 확인 Form과 loading/error가
있다. 서버는 Pydantic 검증 → 중복 확인 → Argon2 Hash → User 추가 → commit → 201
응답 순으로 처리한다.

- 근거: Frontend `RegisterPage.tsx`, Backend `auth.py` Router/Service
- 시연: 잘못된 아이디, 비밀번호 불일치, 정상 가입을 차례로 보여준다.
- 핵심 개념: Frontend 검증은 UX, Backend 검증은 신뢰 경계의 보안이다.

## 항목 8 — 인증 상태 저장과 방식 선택

**답변:** JWT Bearer 인증을 사용한다. Frontend가 Token을 저장하고 새로고침 시
`GET /api/me`로 복원한다. Backend는 JWT 서명·만료를 확인하고 사용자 DB를 다시
조회한다. Stateless 확장성과 Frontend/Backend 분리 배포 때문에 이 방식을 선택했다.

- 근거: `app/services/auth.py`, `app/dependencies.py`, Frontend `AuthContext.tsx`
- 시연: 로그인 후 새로고침해도 Chat 화면과 사용자 상태가 유지됨을 보여준다.
- 핵심 개념: Authentication과 Authorization을 구분한다.

## 항목 9 — 비로그인 401과 공개·보호 API

**답변:** Bearer Token이 없으면 `401 {"detail":"로그인이 필요합니다."}`를 반환한다.
공개 API는 Health·회원가입·로그인이고, 나머지는 일반 사용자 또는 관리자 인증이
필요하다.

- 근거: `login_required_exception()`, API Endpoint 표
- 시연: Token 없이 `/api/me/chats`를 호출한다.
- 핵심 개념: 401은 인증 필요, 403은 인증됐지만 권한 부족이다.

## 항목 10 — 질문 UI, 응답, Loading·Error UX

**답변:** `ChatPage`는 질문 입력, Pending Message, 전송 비활성화, AI 응답 표시,
Network/HTTP 오류 Banner, 기록 Loading Skeleton을 제공한다. 결과가 불명확한 Network
오류에서 질문을 자동 재전송하지 않아 중복 저장도 방지한다.

- 근거: Frontend `ChatPage.tsx`, `ChatMessages.tsx`, `Alert.tsx`
- 시연: 질문 전송 중 Spinner/Pending 상태와 오류 메시지를 보여준다.
- 핵심 개념: 서버 안정성뿐 아니라 사용자가 현재 상태를 이해할 수 있어야 한다.

## 항목 11 — 서버 AI 호출과 메시지 규칙

**답변:** OpenAI 호출은 Backend `AIService`에서만 수행한다. system 메시지 → 최근
3개 user/assistant 쌍 → 현재 질문 순서이며 `gpt-5-nano`, Responses API,
`store=False`를 사용한다.

- 근거: `app/services/ai.py`, `tests/test_ai_service.py`
- 시연: 테스트의 Mock Client가 받은 `input` 순서를 보여준다.
- 핵심 개념: Context Window 비용과 연속성 사이의 균형이다.

## 항목 12 — 질문·응답 저장과 Migration

**답변:** AI 성공 후 `chat_logs`에 user_id, question, response, created_at을 저장한다.
Schema 변경은 Backup → Versioned SQL/Alembic → 사본 테스트 → 운영 적용 → 검증 →
Rollback 순서로 문서화했다.

- 근거: `app/services/chat.py`, README “Schema 변경과 Migration 절차”
- 시연: Chat 전송 전후 `GET /api/me/chats` 또는 SQL 결과를 비교한다.
- 핵심 개념: `create_all()`은 Migration Tool이 아니다.

## 항목 13 — 사용자·관리자 로그 조회

**답변:** 일반 사용자는 `/api/me/chats`와 Chat 화면에서 자기 기록만 보고 삭제한다.
관리자는 `/api/admin/users`로 사용자·대화 수를, `/api/admin/users/{id}/chats`로 선택
사용자의 전체 기록을 읽는다. AdminPage도 구현돼 있다.

- 근거: `app/routers/admin.py`, Frontend `AdminPage.tsx`
- 시연: 일반 계정과 관리자 계정으로 각각 로그인해 화면 차이를 보여준다.
- 핵심 개념: 최소 권한과 소유권 기반 접근 제어다.

## 항목 14 — Timeout, Retry, 대체 응답

**답변:** 시도별 20초 timeout, 추가 3회, 1·2·4초 backoff를 사용한다. 오류 유형에
따라 502·503·504와 한국어 안내를 반환하며 서버는 종료되지 않는다.

- 근거: `app/services/ai.py`, `app/routers/chat.py`
- 시연: Mock timeout 테스트가 총 4회와 backoff를 검증하는 부분을 보여준다.
- 핵심 개념: 재시도 가능한 Transient Failure와 즉시 실패할 Permanent Failure를 구분한다.

## 항목 15 — AI 실패 502와 오류 메시지 표준

**답변:** 잘못된 OpenAI 응답·연결 실패·재시도 불가능한 4xx는 502로 변환한다.
모든 처리 가능한 오류는 `{"detail":"..."}` 계약과 한국어 존댓말을 사용한다.
Timeout은 의미상 504, 한도·일시적 불가는 503으로 더 정확히 구분한다.

- 근거: `map_ai_error()`, Frontend `statusFallbacks`
- 시연: 502 Mock API 테스트와 Frontend Error Alert를 보여준다.
- 핵심 개념: 내부 Stack Trace와 Provider 오류를 사용자에게 직접 노출하지 않는다.

## 항목 16 — Backend·Frontend 동일 입력 검증

**답변:** 질문은 공백 제거 후 1~500자이고 username·password 규칙도 양쪽에서 같다.
Frontend 검증을 우회해도 Backend Pydantic이 422로 거부한다.

- 근거: `app/schemas/auth.py`, `app/schemas/chat.py`, Frontend `utils/validation.ts`
- 시연: 501자 입력의 Frontend 차단과 curl 422를 각각 보여준다.
- 핵심 개념: Client 입력은 신뢰하지 않는다.

## 항목 17 — Schema·Router·Service 분리

**답변:** Pydantic Schema는 `schemas`, HTTP 처리는 `routers`, AI와 업무 Transaction은
`services`, DB Query는 `repositories`로 분리돼 있다.

- 근거: Backend Directory Tree
- 시연: `/api/chat`이 Router → Service → Repository로 내려가는 코드를 순서대로 연다.
- 핵심 개념: SRP와 Testability다.

## 항목 18 — auth, chat, ui 책임과 Endpoint

**답변:** Backend `auth.py`는 register/login/me, `chat.py`는 Chat 생성과 내 기록,
`admin.py`는 운영 조회를 담당한다. UI는 Backend Template가 아니라 별도 Frontend
`pages`와 React Router가 담당한다.

- 근거: `app/routers/`, Frontend `src/App.tsx`
- 시연: Swagger Tag와 React Route를 비교한다.
- 핵심 개념: UI Route와 API Route는 서로 다른 책임이다.

## 항목 19 — Pydantic과 API Version 정책

**답변:** 모든 요청·응답은 Pydantic Schema를 사용한다. 현재 `/api`를 v1 계약으로
간주하며 호환 변경은 기존 경로, 필드 삭제·이름/의미 변경은 `/api/v2`로 제공한다.
변경 PR은 Schema·OpenAPI·테스트·Frontend Type·README를 함께 수정한다.

- 근거: `app/schemas/`, README “API 호환성과 Version 정책”
- 시연: `/openapi.json`에서 Request/Response Schema를 보여준다.
- 핵심 개념: Backend와 Client 간 계약의 하위 호환성이다.

## 항목 20 — 인증 Middleware/Depends 재사용

**답변:** 이 프로젝트는 Cookie Session이 아닌 JWT를 선택했으므로 SessionMiddleware를
등록하지 않는다. 대신 `HTTPBearer`와 `Depends(get_current_user)`를 모든 보호 API에서
재사용하고 관리자·일반 사용자를 추가 Dependency로 분리한다.

- 근거: `app/main.py`, `app/dependencies.py`
- 시연: Router 여러 곳의 동일 Depends 사용을 보여준다.
- 핵심 개념: 평가 문구의 SessionMiddleware는 Session 방식을 선택했을 때의 기준이다.

## 항목 21 — Repository/CRUD 계층과 인터페이스

**답변:** User·Chat Query가 Repository에 있고 `ChatRepository` Protocol이 Service가
필요로 하는 메서드를 정의한다. 복잡한 관리자 사용자·대화 수 Query도 Repository가
추상화한다.

- 근거: `app/repositories/`, `app/repositories/protocols.py`
- 시연: Service 테스트에서 Fake/Mock Repository 주입을 보여준다.
- 핵심 개념: Python Protocol은 명시적 상속 없이 구조가 맞으면 사용할 수 있는 Interface다.

## 항목 22 — 민감정보 환경 변수

**답변:** `Settings`가 `.env`와 운영 환경 변수에서 Secret, DB URL, OpenAI 설정,
CORS를 읽는다. `SecretStr`로 API Key와 JWT Secret의 실수 출력도 줄인다.

- 근거: `app/config.py`
- 시연: 코드에 실제 Key가 없고 Railway Variables에 이름만 존재함을 보여준다.
- 핵심 개념: Secret은 코드·Git·Frontend Bundle·로그에 들어가면 안 된다.

## 항목 23 — `.env.example`과 `.gitignore`

**답변:** `.env.example`은 모든 변수 이름과 로컬/Volume DB 예시를 제공하고,
`.gitignore`는 `.env`, DB 파일, 가상환경과 Cache를 제외한다.

- 근거: `.env.example`, `.gitignore`
- 시연: `git status`에 `.env`가 나타나지 않는지 확인한다.
- 핵심 개념: 예시는 공유하되 실제 값은 공유하지 않는다.

## 항목 24 — PR·Merge 이력

**답변:** Backend와 Frontend 모두 기능 Branch·PR·CI·Merge 이력이 있고 README에
대표 PR과 Release PR 링크가 있다.

- 근거: README PR 증빙 표, GitHub Pull Requests
- 시연: `develop → main` Release PR과 기능 PR의 Files/Commits/Checks를 보여준다.
- 핵심 개념: 결과 코드뿐 아니라 협업 과정도 제출물이다.

## 항목 25 — REST Endpoint 규칙과 conversations 설계

**답변:** 현재 사용자 소유 Collection은 `/api/me/chats`, 관리자 관점은
`/api/admin/users/{user_id}/chats`로 일관되게 설계했다. 현재 MVP에는 대화방 단위
Resource가 없으며, 필요하면 `/api/conversations`와 `/api/conversations/{id}`를 새
Version 또는 호환 Resource로 추가한다는 정책이 문서화돼 있다.

- 근거: Router Path, README API Version 정책
- 시연: Swagger Endpoint 구조를 보여준다.
- 핵심 개념: REST는 Resource 중심의 명사형 URI와 HTTP Method 의미를 사용한다.

## 항목 26 — 비로그인 제한 근거

**답변:** 사용자 기록은 개인 데이터이고 이전 기록은 AI 문맥으로 전송되므로 소유권
확인이 필요하다. 인증 없이 접근하면 정보 노출과 문맥 혼합이 발생할 수 있어 Chat과
기록을 제한한다.

- 근거: README 인증 설명, `get_current_user`
- 시연: 다른 사용자 Token으로 상대 기록을 조회할 Endpoint가 없음을 설명한다.
- 핵심 개념: Privacy와 Data Isolation이다.

## 항목 27 — OpenAI Key 서버 전용

**답변:** Key는 Railway `OPENAI_API_KEY`에서만 읽으며 `AsyncOpenAI` 생성에 사용한다.
Frontend에는 공개 Backend URL만 있고 OpenAI SDK와 Key가 없다.

- 근거: `app/services/ai.py`, Vercel 환경 변수
- 시연: Vercel에는 `VITE_API_BASE_URL`만 있음을 보여준다.
- 핵심 개념: `VITE_` 변수는 Browser에 공개되므로 Secret을 넣으면 안 된다.

## 항목 28 — OpenAI Timeout·예외 정책 문서화

**답변:** 항목 14와 같이 코드와 README에 시도별 timeout, 총 시도 수, backoff,
재시도 대상, 즉시 실패 대상과 최종 사용자 응답을 함께 문서화했다.

- 근거: README “OpenAI 안정성”, `tests/test_ai_service.py`
- 시연: timeout·Rate Limit·Quota·5xx Test 목록을 보여준다.
- 핵심 개념: 문서와 코드 정책이 일치해야 한다.

## 항목 29 — 로그 조회와 운영 활용

**답변:** SQL 실행법뿐 아니라 `request_id`를 이용한 장애 추적, 사용자별 이용 흐름,
반복 오류 분석과 서비스 품질 개선 목적을 README에 설명한다. 원문은 외부 Issue나
Screenshot에 게시하지 않는 운영 원칙도 있다.

- 근거: README “SQL로 대화 로그 확인”, “운영 로그”
- 시연: 특정 `request_id`로 Railway Log와 DB Row를 연결한다.
- 핵심 개념: Observability는 단순 출력이 아니라 문제를 재구성할 수 있는 정보다.

## 항목 30 — 요청·AI·처리 상태·추가 로그 필드 DB 기록

**답변:** 원문 질문·응답은 `chat_logs`, 처리 상태·오류·latency·Origin·Content-Type·
User-Agent는 `request_logs`에 저장한다. 성공한 Chat은 `chat_id`, 사용자는 `user_id`,
전체 이벤트는 `request_id`로 연결한다.

- 근거: `RequestLog` Model, `request_logging_middleware`
- 시연: `scripts/check_logs.sql` 결과의 두 Table Join을 보여준다.
- 핵심 개념: 개인정보 원문과 운영 Metadata를 분리한다.

## 항목 31 — README 설명과 Commit·PR 대조 증빙

**답변:** README 마지막 연결표가 인증, DB·Chat, OpenAI·로그, UI, Release 영역별
Source/Test와 대표 PR을 연결한다. 평가자는 문서 설명 → 실제 파일 → 테스트 → PR
순서로 일치 여부를 확인할 수 있다.

- 근거: README “주요 PR과 Git 기여 증빙”
- 시연: 한 행을 선택해 Source와 대표 PR을 차례로 연다.
- 핵심 개념: Traceability는 요구사항에서 구현과 변경 이력까지 연결하는 것이다.

---

## 14. 발표 시 반드시 구분해서 말할 개념

### Authentication vs Authorization

- Authentication(인증): “누구인가?” — 로그인, JWT 검증
- Authorization(인가): “무엇을 할 수 있는가?” — 일반 사용자/관리자 API 제한

### 401 vs 403

- 401: Token이 없거나 유효하지 않아 로그인 필요
- 403: 로그인은 됐지만 해당 기능 권한 없음

### Schema vs Model

- Pydantic Schema: 외부 HTTP 데이터의 형식과 검증
- SQLAlchemy Model: DB Table과 Python 객체 Mapping

### Router vs Service vs Repository

- Router: HTTP
- Service: 업무 규칙과 Transaction
- Repository: DB Query

### Hashing vs Encryption

- 비밀번호는 복호화할 필요가 없으므로 단방향 Argon2 Hash를 사용한다.
- 로그인 때 입력 비밀번호를 같은 알고리즘으로 검증한다.

### CORS vs Authentication

- CORS: Browser가 다른 Origin 요청을 허용할지 결정
- Authentication: API 사용자가 누구인지 확인
- CORS를 허용했다고 누구나 보호 API를 사용할 수 있는 것은 아니다.

### Timeout vs Retry

- Timeout: 한 번의 시도를 얼마나 기다릴지
- Retry: 일시적 실패 후 몇 번 다시 시도할지

### CI vs CD

- CI: Commit/PR마다 테스트·lint·build로 코드 품질 검증
- CD: 통과한 Release를 Railway/Vercel에 배포

### Container vs Volume

- Container Filesystem: 재배포 시 교체될 수 있음
- Volume: Container와 별도로 유지되는 영속 Storage

### Unit vs Integration Test

- Unit: Service나 함수 하나를 Mock으로 검증
- Integration/API: Router, Dependency, DB 흐름을 함께 검증
- 실제 Production Smoke Test: 배포된 Frontend/Backend/OpenAI/Volume을 직접 검증

---

## 15. 예상 질문과 짧은 답변

### “왜 최근 대화가 3개인가요?”

연속성을 제공하면서 Token 비용·응답 지연·개인정보 전송량을 제한하는 MVP 기준이다.
설정 가능 값으로 발전시킬 수 있다.

### “AI가 실패하면 DB에는 무엇이 남나요?”

실패한 질문·가짜 응답은 `chat_logs`에 남지 않는다. 대신 `request_logs`와 Railway
Application Log에 상태 코드, 오류 Type, latency와 `request_id`가 남는다.

### “왜 관리자도 Chat을 못 하나요?”

운영 조회 계정과 일반 사용자 데이터를 분리해 권한 오용과 관리자 기록 노출을 줄이기
위해서다. 관리자 계정은 운영 전용이다.

### “SQLite가 Production에 적합한가요?”

이 과제 규모와 단일 Replica MVP에는 단순하고 평가자가 직접 확인하기 쉽다. Write
동시성이나 수평 확장이 커지면 PostgreSQL과 Alembic으로 전환하는 것이 적절하다.

### “왜 OpenAI SDK 재시도를 껐나요?”

SDK와 앱이 동시에 재시도하면 실제 시도 횟수와 지연이 예측하기 어렵다. 앱에서 한
정책으로 timeout, 횟수, backoff와 로그를 통제하기 위해 `max_retries=0`을 사용한다.

### “Health Check가 DB와 OpenAI도 검사하나요?”

아니다. Process Readiness를 빠르고 안정적으로 확인하기 위해 항상 `{"status":"ok"}`를
반환하고 외부 의존성을 호출하지 않는다. DB/OpenAI는 별도 Smoke Test와 운영 로그로
확인한다.

### “왜 모든 Header를 저장하지 않나요?”

Authorization, Cookie 등 민감정보가 섞일 수 있기 때문이다. 운영에 필요한 Origin,
Content-Type, User-Agent만 Allow-list로 저장한다.

### “Token이 탈취되면 어떻게 하나요?”

현재 MVP는 만료 시간이 있는 Access Token을 사용한다. 고도화 시 짧은 Access Token,
HttpOnly Refresh Cookie, Token Rotation·Revoke 목록, CSP를 추가한다.

### “대화방 Sidebar를 완전한 ChatGPT처럼 만들 수 있나요?”

현재 `chat_logs`는 사용자별 단일 기록 Collection이다. 과거 질문 목록 Sidebar는
Frontend만으로 만들 수 있지만, 여러 대화방·제목·개별 대화 삭제가 필요하면
`conversations`와 `messages` 관계 및 REST API를 새 Version으로 설계해야 한다.

### “관리자는 어떻게 만드나요?”

먼저 일반 회원가입한 뒤 Railway 운영 Shell에서
`python -m scripts.grant_admin <username>`을 실행한다. 공개 승격 API는 없다.

### “가장 중요한 운영 추적 값은 무엇인가요?”

`request_id`다. 응답 Header, AI 이벤트, DB 저장 이벤트, 완료 로그와 `request_logs`를
같은 값으로 연결한다.

---

## 16. 최종 평가 당일 시연 순서

1. 두 GitHub Repository와 README를 연다.
2. Vercel Frontend가 외부에서 접속되는지 확인한다.
3. Railway `/health`의 200과 `X-Request-ID`를 확인한다.
4. 새 일반 계정을 회원가입한다.
5. 잘못된 로그인 오류와 정상 로그인을 각각 보여준다.
6. 500자 제한과 공백 질문 차단을 보여준다.
7. 정상 질문을 보내 Pending UI와 AI 응답을 확인한다.
8. 기록 화면에서 방금 질문·답변이 저장됐는지 확인한다.
9. 새로고침 후 인증과 기록이 유지되는지 확인한다.
10. Railway Log에서 해당 `request_id`의 요청→AI→DB→완료 이벤트를 찾는다.
11. 관리자 계정으로 로그인해 사용자 목록과 대화 기록을 확인한다.
12. Swagger에서 API와 오류 Response Table을 보여준다.
13. `scripts/check_logs.sql`과 DB ERD를 보여준다.
14. Backend pytest와 Frontend lint·test·build CI 성공을 보여준다.
15. 대표 기능 PR과 `develop → main` Release PR을 보여준다.

### 평가 직전 체크리스트

- [ ] Vercel Production이 `Ready`
- [ ] Railway Deployment가 `ACTIVE`
- [ ] `/health` 200
- [ ] Railway `/data` Volume 연결
- [ ] `DATABASE_URL=sqlite:////data/chatflow.db`
- [ ] `CORS_ORIGINS=https://chat-flow-topaz.vercel.app`
- [ ] Vercel `VITE_API_BASE_URL`이 Railway Backend URL
- [ ] 일반 사용자 회원가입·로그인·Chat·기록 조회
- [ ] 관리자 로그인·사용자/기록 조회
- [ ] 재시작 후 DB 데이터 유지
- [ ] Backend CI와 Frontend CI 성공
- [ ] `.env`, API Key, JWT, 비밀번호가 Git/로그에 없음
- [ ] 역할·PR·Commit 증빙 링크 정상
- [ ] 팀원별 유의미한 Commit 10회 이상 최종 확인

---

## 17. 최종 한 문장

ChatFlow는 “로그인한 사용자 질문을 안전하게 AI에 전달하고, 최근 문맥을 반영한 답변과
운영 추적 정보를 영속적으로 저장하며, 장애가 발생해도 예측 가능한 상태 코드와 로그로
복구 가능한” Frontend–Backend 통합 AI 웹 서비스다.
