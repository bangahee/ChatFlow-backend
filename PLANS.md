# ChatFlow Backend 3인 개발 계획

## 1. 문서 목적

이 문서는 기존 FastAPI 프로토타입을 프론트엔드와 분리된 **API 전용 백엔드**로 전환하기 위한 3인 협업 계획이다.

다음 목표를 동시에 만족하는 것을 기준으로 한다.

- 세 명이 겹치지 않는 영역을 담당한다.
- 모든 변경은 Issue, 기능 브랜치, Pull Request 단위로 남긴다.
- 각 팀원이 기능 코드와 해당 기능의 테스트를 함께 작성한다.
- 초기에 API 계약과 모듈 경계를 고정하여 병렬 작업 중 충돌을 줄인다.
- 최종 결과물은 React 등 별도 프론트엔드가 호출할 수 있는 JSON REST API이다.
- 실제 OpenAI API를 호출하지 않아도 자동 테스트가 가능해야 한다.
- Railway 등 외부 환경에 배포할 수 있어야 한다.

---

## 2. 현재 프로토타입에서 유지할 것과 제거할 것

### 유지할 기능

- FastAPI 애플리케이션
- 회원가입과 로그인
- 비밀번호 해싱
- JWT Bearer 인증
- 사용자별 대화 기록
- 최근 3개 대화를 이용한 AI 문맥 구성
- OpenAI API 호출
- AI 호출 타임아웃과 재시도
- SQLite 및 SQLAlchemy
- 요청 단위 로깅
- Railway 배포 설정

### 제거할 기능

- `/`, `/login`, `/register`, `/chat`의 HTML 화면 응답
- Jinja2 템플릿 렌더링
- `templates/` 디렉터리
- HTML 화면에서만 사용하던 JavaScript와 CSS
- 백엔드 내부의 프론트엔드 페이지 이동 처리
- API에서 사용하지 않는 `jinja2` 의존성

### 새로 보강할 기능

- 프론트엔드 Origin을 제한하는 CORS 설정
- API 요청 및 응답 Pydantic Schema
- 일관된 HTTP 상태 코드와 오류 응답
- `/health` 상태 확인 API
- 테스트용 DB와 실제 DB 분리
- OpenAI API Mock 기반 테스트
- GitHub Actions 자동 테스트
- API 명세와 환경 변수 문서

---

## 3. 확정할 MVP 범위

### 필수 API

| Method | Endpoint | 인증 | 성공 상태 | 용도 |
|---|---|---:|---:|---|
| `GET` | `/health` | X | 200 | 서버 상태 확인 |
| `POST` | `/api/auth/register` | X | 201 | 회원가입 |
| `POST` | `/api/auth/login` | X | 200 | JWT 발급 |
| `POST` | `/api/chat` | O | 201 | 질문 전송, AI 응답 생성 및 저장 |
| `GET` | `/api/me/chats` | O | 200 | 로그인 사용자의 대화 기록 조회 |
| `DELETE` | `/api/me/chats` | O | 200 | 로그인 사용자의 전체 대화 기록 삭제 |

### MVP 이후 선택 기능

다음 항목은 필수 기능을 모두 완료한 뒤 별도 Issue로 진행한다.

- `GET /api/me` 사용자 정보 조회
- 개별 대화 삭제
- 대화 기록 페이지네이션
- Refresh Token
- 로그아웃 Token 차단 목록
- 관리자 API
- Alembic 데이터베이스 마이그레이션
- 스트리밍 AI 응답

선택 기능을 먼저 구현하여 필수 일정에 영향을 주지 않는다.

---

## 4. API 계약

API 계약은 병렬 작업을 시작하기 전에 세 명이 검토하고 확정한다. 계약을 변경해야 할 때는 코드보다 문서를 먼저 수정하는 PR을 만든다.

### 4-1. 공통 규칙

- 요청과 응답은 JSON을 사용한다.
- 인증이 필요한 요청은 다음 Header를 사용한다.

```http
Authorization: Bearer <access_token>
```

- 서버 시간은 UTC 기준 ISO 8601 문자열로 반환한다.
- 사용자가 입력한 비밀번호, JWT, OpenAI API Key는 로그에 기록하지 않는다.
- Pydantic 검증 실패는 FastAPI 기본 `422` 응답을 사용한다.
- 처리 가능한 비즈니스 오류는 `detail` 문자열을 포함한다.

```json
{
  "detail": "오류 설명"
}
```

### 4-2. 회원가입

```http
POST /api/auth/register
Content-Type: application/json
```

```json
{
  "username": "chat_user",
  "password": "password123"
}
```

성공 응답:

```json
{
  "id": 1,
  "username": "chat_user",
  "created_at": "2026-08-20T03:00:00Z"
}
```

오류:

- `400`: 이미 존재하는 아이디
- `422`: 아이디 또는 비밀번호 형식 오류
- `500`: 예상하지 못한 DB 오류

### 4-3. 로그인

```http
POST /api/auth/login
Content-Type: application/json
```

```json
{
  "username": "chat_user",
  "password": "password123"
}
```

성공 응답:

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "expires_in": 86400
}
```

오류:

- `401`: 아이디 또는 비밀번호 불일치
- `422`: 요청 형식 오류

현재 프로토타입처럼 JSON 로그인 API를 유지한다. Swagger 인증 UI와 JSON 로그인 방식의 불일치를 피하기 위해 인증 의존성은 `HTTPBearer` 사용을 기본안으로 한다. OAuth2 Password Flow가 꼭 필요해지면 별도의 Form 기반 Token Endpoint를 추가 Issue로 논의한다.

### 4-4. 질문 전송

```http
POST /api/chat
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "question": "이 프로젝트의 구조를 설명해 줘"
}
```

성공 응답:

```json
{
  "id": 10,
  "question": "이 프로젝트의 구조를 설명해 줘",
  "response": "응답 내용",
  "created_at": "2026-08-20T03:10:00Z",
  "request_id": "uuid"
}
```

오류:

- `401`: Token 없음, 만료 또는 변조
- `422`: 공백 질문 또는 500자 초과
- `502`: OpenAI의 잘못된 응답 또는 연결 실패
- `503`: OpenAI 요청 한도 또는 일시적 사용 불가
- `504`: OpenAI 호출 최종 타임아웃
- `500`: ChatLog 저장 실패

AI 호출이 실패한 경우 실패 안내 문자열을 정상 AI 답변처럼 DB에 저장하지 않는다.

### 4-5. 대화 기록 조회

```http
GET /api/me/chats
Authorization: Bearer <access_token>
```

성공 응답:

```json
{
  "items": [
    {
      "id": 10,
      "question": "질문",
      "response": "응답",
      "created_at": "2026-08-20T03:10:00Z"
    }
  ],
  "count": 1
}
```

정렬 순서는 오래된 대화부터 최신 대화 순서로 고정한다.

### 4-6. 대화 기록 삭제

```http
DELETE /api/me/chats
Authorization: Bearer <access_token>
```

성공 응답:

```json
{
  "message": "대화 기록이 삭제되었습니다.",
  "deleted_count": 3
}
```

반드시 로그인한 사용자의 기록만 삭제한다.

### 4-7. 상태 확인

```http
GET /health
```

```json
{
  "status": "ok"
}
```

기본 Health Check에서는 OpenAI API를 실제 호출하지 않는다.

---

## 5. 목표 디렉터리 구조

```text
ChatFlow-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── dependencies.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── chat.py
│   │   └── health.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── chat.py
│   │   └── common.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── chat.py
│   └── services/
│       ├── __init__.py
│       ├── auth.py
│       ├── chat.py
│       └── ai.py
├── tests/
│   ├── conftest.py
│   ├── test_auth_api.py
│   ├── test_chat_api.py
│   ├── test_chat_repository.py
│   ├── test_ai_service.py
│   └── test_health.py
├── .github/
│   └── workflows/
│       └── test.yml
├── .env.example
├── .gitignore
├── requirements.txt
├── railway.json
├── README.md
└── PLANS.md
```

### 계층별 책임

```text
Router
  → HTTP 요청/응답, Depends, 상태 코드

Schema
  → 입력값 검증, 응답 구조

Service
  → 인증, 채팅, AI 등의 업무 흐름

Repository
  → SQLAlchemy 조회, 저장, 삭제

Model
  → DB 테이블과 관계
```

Router에서 OpenAI SDK를 직접 호출하거나 긴 SQLAlchemy Query를 작성하지 않는다. Service에서 HTTP 객체를 직접 다루지 않고, Repository에서 HTTPException을 발생시키지 않는다.

---

## 6. 3인 역할 분담

담당자는 `A=박주영`, `B=김승우`, `C=반가희`로 지정한다. GitHub Issue와 Pull Request에도 같은 담당 표기를 사용한다.

### 담당자 A — 박주영 — API 기반 및 인증

주요 소유 파일:

```text
app/main.py
app/config.py
app/dependencies.py
app/routers/auth.py
app/schemas/auth.py
app/services/auth.py
.env.example
requirements.txt
```

담당 작업:

1. FastAPI API 전용 애플리케이션 초기화
2. HTML/Jinja2 연결 제거
3. CORS 환경 설정
4. 공통 설정 객체 구성
5. 회원가입 요청 및 응답 Schema
6. 로그인 요청 및 Token 응답 Schema
7. 비밀번호 해싱과 검증
8. JWT 발급, 만료 및 검증
9. `get_current_user` 인증 의존성
10. 회원가입과 로그인 Router
11. 인증 성공·실패 테스트
12. 환경 변수와 Dependency 최종 관리

완료 조건:

- 회원가입과 로그인이 JSON으로 동작한다.
- 중복 아이디와 잘못된 비밀번호가 구분된다.
- 보호 API에서 유효한 사용자를 식별할 수 있다.
- Swagger에서 Bearer Token 입력이 가능하다.
- 실제 Secret이 저장소에 포함되지 않는다.

### 담당자 B — 김승우 — Database 및 Chat 기능

주요 소유 파일:

```text
app/database.py
app/models.py
app/repositories/user.py
app/repositories/chat.py
app/routers/chat.py
app/schemas/chat.py
app/services/chat.py
tests/conftest.py
```

담당 작업:

1. SQLAlchemy Engine 및 Session 관리
2. 테스트 DB Dependency Override 기반 마련
3. `User`, `ChatLog` Model과 관계 구성
4. username 고유 제약조건
5. User Repository 구현
6. 사용자별 최근 3개 ChatLog 조회
7. ChatLog 저장과 rollback
8. 사용자별 ChatLog 전체 조회
9. 사용자별 ChatLog 전체 삭제
10. Chat Service 업무 흐름
11. Chat Router와 응답 Schema
12. 사용자 간 데이터 격리 테스트

완료 조건:

- 한 사용자의 데이터가 다른 사용자에게 노출되지 않는다.
- 최근 대화 3개가 시간 순서에 맞게 AI Service에 전달된다.
- AI 성공 이후에만 ChatLog가 저장된다.
- DB 실패 시 rollback 후 500 응답이 반환된다.
- 테스트는 실제 운영 DB 파일을 사용하지 않는다.

### 담당자 C — 반가희 — AI, 안정성, 자동화 및 배포

주요 소유 파일:

```text
app/services/ai.py
app/routers/health.py
app/schemas/common.py
tests/test_ai_service.py
tests/test_health.py
.github/workflows/test.yml
railway.json
README.md의 실행/배포/API 항목
```

담당 작업:

1. Async OpenAI Client 구성
2. 최근 대화 Context 변환
3. System/User/Assistant Message 순서 보장
4. 하드 타임아웃 적용
5. 최대 3회 Retry
6. Exponential Backoff
7. Rate Limit, 연결, API 상태, 빈 응답 처리
8. AI 오류를 도메인 오류로 변환
9. AI 호출 시작·성공·실패 Logging
10. OpenAI Mock 단위 테스트
11. `/health` 구현과 테스트
12. GitHub Actions 및 Railway 배포 설정

완료 조건:

- 테스트 중 실제 OpenAI API를 호출하지 않는다.
- 재시도 가능한 오류와 즉시 실패할 오류가 구분된다.
- 최종 오류가 정해진 HTTP 상태로 변환될 수 있다.
- API Key나 질문 전체가 로그에 출력되지 않는다.
- PR마다 `pytest`가 자동 실행된다.
- Railway에서 `app.main:app`을 실행할 수 있다.

---

## 7. 모듈 간 사전 합의 Interface

병렬 작업을 위해 다음 함수의 입력과 출력 형태를 먼저 고정한다. 구체적인 클래스 이름은 첫 구조 PR에서 확정할 수 있지만 의미는 바꾸지 않는다.

### User Repository

```python
get_user_by_username(db, username) -> User | None
create_user(db, username, hashed_password) -> User
```

### Chat Repository

```python
get_recent_chats(db, user_id, limit=3) -> list[ChatLog]
create_chat(db, user_id, question, response) -> ChatLog
list_user_chats(db, user_id) -> list[ChatLog]
delete_user_chats(db, user_id) -> int
```

### AI Service

```python
async generate_ai_response(
    question: str,
    history: list[ChatLog],
    request_id: str,
) -> str
```

### Chat Service 흐름

```text
current_user 확인
→ 최근 3개 대화 조회
→ AI Service 호출
→ 성공 응답 검증
→ ChatLog 저장
→ Chat Response 반환
```

Interface 변경이 필요하면 관련 담당자 두 명의 승인을 받은 뒤 별도 PR에서 먼저 변경한다.

---

## 8. 파일 충돌 방지 규칙

### 공통 파일 소유권

| 파일 | 기본 담당 | 변경 규칙 |
|---|---|---|
| `app/main.py` | 박주영(A) | Router 추가 요청은 박주영이 반영하거나 박주영의 리뷰 필요 |
| `app/config.py` | 박주영(A) | 새 환경 변수는 Issue에 먼저 기록 |
| `requirements.txt` | 박주영(A) | 필요한 패키지와 이유를 PR에 작성 |
| `app/models.py` | 김승우(B) | Schema 변경 시 박주영과 반가희에게 공지 |
| `tests/conftest.py` | 김승우(B) | 공용 Fixture 변경은 기존 테스트 전체 실행 |
| `app/services/ai.py` | 반가희(C) | 함수 계약 변경 시 김승우의 승인 필요 |
| `railway.json` | 반가희(C) | 실행 경로 변경 시 박주영의 승인 필요 |
| `README.md` | 반가희(C) | 기능 담당자가 내용 초안을 제공 |

### 작업 시작 전 규칙

1. Issue에 수정할 파일 목록을 적는다.
2. 다른 진행 중 Issue와 파일이 겹치면 먼저 범위를 조정한다.
3. 공통 파일 변경이 필요하면 해당 파일 담당자에게 알린다.
4. 하나의 PR에 다른 담당자의 기능까지 함께 구현하지 않는다.
5. 큰 파일 이동은 기능 개발 전에 별도 구조 PR로 끝낸다.

---

## 9. Git 및 Pull Request 운영

### 브랜치

- `main`: 항상 실행 및 배포 가능한 상태
- 기능 개발: 최신 `main`에서 짧은 브랜치를 생성
- `main` 직접 Push 금지

브랜치 예시:

```text
refactor/api-only-scaffold
feat/auth-register
feat/auth-login-jwt
feat/database-models
feat/chat-history
feat/openai-client
fix/chat-transaction
test/auth-api
ci/pytest
docs/backend-api
```

### 기본 명령 흐름

```bash
git switch main
git pull --ff-only
git switch -c feat/auth-register

# 작업 및 테스트

git add -- <이번 작업 파일>
git commit -m "feat(auth): 회원가입 API 구현"
git push -u origin feat/auth-register
```

### Commit 형식

```text
<type>(<scope>): <한글 작업 내용>
```

예시:

```text
refactor(app): API 전용 애플리케이션 구조 생성
feat(auth): 비밀번호 해싱 로직 추가
feat(auth): JWT access token 발급 구현
feat(db): User와 ChatLog 모델 추가
feat(chat): 사용자별 대화 기록 조회 구현
feat(ai): 최근 대화 context 구성
fix(ai): timeout 재시도 조건 수정
test(chat): 다른 사용자 기록 격리 검증 추가
ci(test): pull request pytest workflow 추가
docs(api): 인증 API 요청과 응답 예시 추가
```

### PR 크기

- 하나의 PR은 하나의 Issue를 해결한다.
- 권장 변경 규모는 리뷰 가능한 100~400줄이다.
- 구조 변경과 기능 변경을 같은 PR에 섞지 않는다.
- 각 PR에 관련 테스트 또는 수동 검증 방법을 포함한다.
- PR 본문에 `Closes #Issue번호`를 작성한다.

### PR 병합 조건

- [ ] 담당 기능 테스트 통과
- [ ] 전체 `pytest` 통과
- [ ] 다른 팀원 1명 이상 승인
- [ ] API 계약 준수
- [ ] `.env`, Key, Token 미포함
- [ ] Debug 출력 제거
- [ ] 최신 `main` 반영
- [ ] 문서 변경 필요 여부 확인

PR 병합 방식은 팀에서 한 가지로 통일한다. 여러 개의 의미 있는 커밋 이력을 보존해야 하므로 `Rebase and merge`를 기본안으로 사용한다.

---

## 10. 단계별 실행 순서

### Phase 0 — 계약과 작업판 준비

세 명이 함께 진행한다.

1. 이 문서의 API Endpoint와 JSON 형식 확인
2. 모듈 Interface 확인
3. GitHub Issue 생성
4. 담당자 지정
5. `main` 브랜치 보호 설정
6. PR Template 준비
7. 첫 통합 일정 결정

완료 기준:

- 필수 API의 요청/응답/오류 상태가 합의되어 있다.
- 첫 번째 작업 Issue가 모두 생성되어 있다.
- 각 Issue의 담당자와 수정 파일이 지정되어 있다.

### Phase 1 — API 전용 Scaffold

박주영(A)이 먼저 수행하고 작은 PR로 병합한다.

작업:

- `app/` 패키지 생성
- `routers`, `schemas`, `services`, `repositories` 생성
- `app/main.py` 생성
- API Router 등록 구조 생성
- Jinja2 의존성 제거 계획 반영
- 기본 CORS와 설정 구조 생성
- 테스트 실행 명령 확인

다른 담당자는 이 PR이 병합되기 전에 같은 구조를 별도로 만들지 않는다.

완료 기준:

```bash
uvicorn app.main:app --reload
```

명령으로 서버가 실행되고 `/docs`가 열린다.

### Phase 2 — DB 기반과 AI 기반 병렬 개발

Phase 1 병합 후 김승우(B)와 반가희(C)가 동시에 진행한다.

### 담당자 B — 김승우

- Database Session
- User/ChatLog Model
- User/Chat Repository
- 테스트용 SQLite Fixture

### 담당자 C — 반가희

- AI Service Interface
- OpenAI Client
- Context Builder
- Mock 기반 AI 단위 테스트

### 담당자 A — 박주영

- 인증 Schema
- 비밀번호 Hashing
- JWT Utility
- CORS 환경 변수

완료 기준:

- 박주영(A)의 인증 Utility 단위 테스트 통과
- 김승우(B)의 Model과 Repository 테스트 통과
- 반가희(C)의 AI Mock 테스트 통과
- 세 영역이 서로의 내부 구현을 직접 참조하지 않는다.

### Phase 3 — 기능 API 병렬 개발

Phase 2의 기반 PR이 병합된 뒤 진행한다.

### 담당자 A — 박주영

- 회원가입 API
- 로그인 API
- Bearer 인증 Dependency
- 인증 API 테스트

### 담당자 B — 김승우

- POST Chat API
- GET Chat History API
- DELETE Chat History API
- DB Transaction 및 사용자 격리 테스트

### 담당자 C — 반가희

- Timeout과 Retry
- OpenAI 오류 Mapping
- AI Logging
- Health API와 CI

완료 기준:

- 각 Endpoint가 API 계약대로 응답한다.
- 보호 API는 Token 없이 호출할 수 없다.
- Chat API 테스트는 OpenAI를 Mock 처리한다.

### Phase 4 — 통합

세 명이 함께 통합하되 수정 담당자는 파일 소유권을 따른다.

통합 시나리오:

```text
회원가입
→ 로그인
→ JWT 획득
→ 질문 전송
→ AI Mock 또는 실제 개발 Key 응답
→ ChatLog 저장 확인
→ 기록 조회
→ 기록 삭제
→ 빈 기록 확인
```

추가 검증:

- 사용자 A가 사용자 B의 기록을 볼 수 없는지 확인
- 만료 또는 변조 Token이 401인지 확인
- 공백 질문과 501자 질문이 422인지 확인
- AI Timeout이 504인지 확인
- AI 실패 시 ChatLog가 저장되지 않는지 확인
- DB 실패 시 rollback되는지 확인

### Phase 5 — 배포 및 프론트엔드 연결

### Backend

- Railway 환경 변수 등록
- SQLite Persistent Volume 연결
- Railway 실행 명령 확인
- Production CORS Origin에 프론트엔드 URL 등록
- `/health` 외부 호출 확인
- `/docs` 공개 여부 결정

### Frontend 연동 확인

- Backend URL을 프론트엔드 환경 변수로 전달
- 로그인 응답 필드 일치 확인
- Authorization Header 확인
- 모든 시간 필드가 UTC ISO 8601인지 확인
- 오류 응답 `detail` 처리 확인

### Phase 6 — 최종 검증

- 전체 테스트 실행
- 새 환경에서 설치 및 실행 확인
- 실제 배포 URL로 핵심 시나리오 확인
- OpenAPI 문서와 README 비교
- 환경 변수 누락 여부 확인
- GitHub Secret Scan 확인
- 각 팀원의 Issue, PR, Review, Commit 기록 확인
- Release Tag 생성

---

## 11. 팀원별 권장 Issue 및 Commit 계획

커밋 수를 늘리기 위한 의미 없는 변경은 만들지 않는다. 아래 작업은 서로 독립적으로 검증할 수 있는 자연스러운 단위다.

### 담당자 A — 박주영

1. `refactor(app): API 전용 패키지 구조 생성`
2. `feat(config): 환경 변수 설정 객체 추가`
3. `feat(cors): 허용 origin 기반 CORS 적용`
4. `feat(auth): 회원가입 요청 검증 schema 추가`
5. `feat(auth): 비밀번호 hash와 검증 구현`
6. `feat(auth): JWT 발급과 만료 검증 구현`
7. `feat(auth): 회원가입 API 구현`
8. `feat(auth): 로그인 API 구현`
9. `feat(auth): current user 의존성 추가`
10. `test(auth): 인증 API 성공과 실패 테스트 추가`
11. `fix(auth): 인증 테스트에서 발견된 오류 수정`
12. `chore(deps): API 전용 의존성 정리`

### 담당자 B — 김승우

1. `feat(db): SQLAlchemy session 구성`
2. `feat(db): User 모델과 제약조건 추가`
3. `feat(db): ChatLog 모델과 관계 추가`
4. `feat(user): 사용자 repository 구현`
5. `feat(chat): 최근 대화 조회 repository 구현`
6. `feat(chat): 대화 저장과 rollback 구현`
7. `feat(chat): 사용자별 기록 조회 구현`
8. `feat(chat): 사용자별 기록 삭제 구현`
9. `feat(chat): chat service 구현`
10. `feat(chat): chat router와 response schema 추가`
11. `test(chat): 사용자 데이터 격리 테스트 추가`
12. `fix(chat): chat transaction 오류 수정`

### 담당자 C — 반가희

1. `feat(ai): async OpenAI client 구성`
2. `feat(ai): 최근 대화 context builder 구현`
3. `feat(ai): OpenAI 응답 추출과 빈 응답 처리`
4. `feat(ai): AI 호출 timeout 적용`
5. `feat(ai): 최대 재시도와 backoff 구현`
6. `feat(ai): rate limit과 connection 오류 처리`
7. `feat(log): AI 요청 추적 logging 추가`
8. `test(ai): AI 성공 응답 mock 테스트 추가`
9. `test(ai): timeout과 retry 테스트 추가`
10. `feat(health): health check API 추가`
11. `ci(test): pull request pytest workflow 추가`
12. `build(railway): backend 실행 설정 추가`

실제 커밋은 해당 변경이 완성되고 테스트 가능한 시점에 생성한다. 한 줄 변경을 억지로 분리하거나 동작하지 않는 중간 상태를 `main`에 병합하지 않는다.

---

## 12. 테스트 계획

### 테스트 원칙

- `pytest`와 FastAPI `TestClient` 또는 `httpx.AsyncClient`를 사용한다.
- 테스트마다 격리된 임시 SQLite DB를 사용한다.
- 실제 `.env`를 읽지 않도록 테스트 설정을 분리한다.
- 실제 OpenAI API를 호출하지 않는다.
- 시간, Retry 대기, 외부 응답은 Mock 또는 Dependency Injection으로 제어한다.

### 인증 테스트

- [ ] 회원가입 성공은 201
- [ ] 중복 아이디는 400
- [ ] 짧은 username은 422
- [ ] 짧은 password는 422
- [ ] 비밀번호가 평문으로 저장되지 않음
- [ ] 로그인 성공 시 Token 발급
- [ ] 잘못된 비밀번호는 401
- [ ] 존재하지 않는 사용자는 401
- [ ] 변조 Token은 401
- [ ] 만료 Token은 401

### Chat API 테스트

- [ ] Token 없는 질문은 401
- [ ] 정상 질문은 201
- [ ] 공백 질문은 422
- [ ] 500자는 허용
- [ ] 501자는 422
- [ ] AI 응답과 ChatLog 저장값이 일치
- [ ] AI 실패 시 ChatLog 미저장
- [ ] 사용자별 기록만 조회
- [ ] 기록 정렬 순서 확인
- [ ] 사용자별 기록만 삭제
- [ ] 삭제 수 `deleted_count` 확인

### AI 테스트

- [ ] 최근 3개 대화만 전달
- [ ] 과거에서 최신 순서로 Context 구성
- [ ] System Message 포함
- [ ] 현재 질문이 마지막 User Message
- [ ] 정상 응답 문자열 추출
- [ ] 빈 응답 처리
- [ ] Timeout 재시도 횟수 확인
- [ ] Exponential Backoff 값 확인
- [ ] Rate Limit 처리
- [ ] Connection Error 처리
- [ ] 4xx 즉시 실패 처리
- [ ] 5xx 재시도 처리

### 통합 테스트

- [ ] 회원가입부터 기록 삭제까지 전체 흐름
- [ ] 두 사용자 간 데이터 격리
- [ ] DB rollback 이후 다음 요청 정상 처리
- [ ] CORS Preflight 허용 Origin 확인
- [ ] 허용되지 않은 Origin 차단 확인
- [ ] `/health` 200 확인

---

## 13. 환경 변수

`.env.example`에는 이름과 안전한 예시만 작성한다.

```env
APP_ENV=development
SECRET_KEY=change-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./chatflow.db
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-nano
OPENAI_TIMEOUT_SECONDS=20
OPENAI_MAX_RETRIES=3
CORS_ORIGINS=http://localhost:5173
```

Production에서는 `CORS_ORIGINS`에 실제 Vercel Origin만 등록한다. `SECRET_KEY`와 `OPENAI_API_KEY`의 실제 값은 GitHub 및 Railway Secret으로 관리한다.

---

## 14. Logging 계획

모든 Chat 요청은 하나의 `request_id`로 연결한다.

필수 이벤트:

```text
request_received
auth_failed
ai_call_started
ai_call_succeeded
ai_call_failed
db_save_succeeded
db_save_failed
request_completed
```

권장 필드:

```text
request_id
user_id
path
method
status_code
latency_ms
attempt
error_type
```

기록하지 않을 값:

```text
password
hashed_password
JWT 전체 문자열
OpenAI API Key
사용자 질문 전체
AI 응답 전체
```

질문과 응답은 길이만 기록한다.

---

## 15. 배포 계획

### 실행 명령

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Railway 확인 항목

- [ ] GitHub Backend Repository 연결
- [ ] Python 의존성 설치 성공
- [ ] Uvicorn 실행 성공
- [ ] 모든 환경 변수 등록
- [ ] SQLite Persistent Volume 경로와 `DATABASE_URL` 일치
- [ ] `/health` 200
- [ ] 회원가입/로그인 정상 동작
- [ ] OpenAI 호출 정상 동작
- [ ] 재배포 후 사용자와 ChatLog 유지
- [ ] Frontend Origin CORS 허용
- [ ] 서버 로그에 Key와 Token이 노출되지 않음

---

## 16. Definition of Done

하나의 Issue는 다음 조건을 모두 만족해야 완료로 처리한다.

- [ ] Issue의 인수 조건을 만족한다.
- [ ] 담당 영역에 맞는 파일만 수정했다.
- [ ] 새 로직에 대한 테스트가 있다.
- [ ] 관련 테스트와 전체 테스트가 통과한다.
- [ ] API 계약을 변경하지 않았다.
- [ ] 계약 변경 시 문서 PR이 선행되었다.
- [ ] 예외와 실패 경로를 처리했다.
- [ ] 민감정보를 포함하지 않았다.
- [ ] 불필요한 출력과 주석을 제거했다.
- [ ] 다른 팀원에게 PR Review를 받았다.
- [ ] 필요한 문서와 `.env.example`을 갱신했다.
- [ ] `main`에 병합된 뒤에도 CI가 통과한다.

---

## 17. 최종 완료 기준

프로젝트는 다음 조건을 모두 만족할 때 API 전용 전환 완료로 판단한다.

- [ ] HTML Template Route가 없다.
- [ ] 백엔드가 JSON API만 제공한다.
- [ ] Jinja2 및 불필요한 Frontend 의존성이 제거되었다.
- [ ] 별도 Frontend Origin에서 CORS 요청이 가능하다.
- [ ] 회원가입, 로그인, JWT 인증이 동작한다.
- [ ] 로그인 사용자만 Chat API를 사용할 수 있다.
- [ ] 최근 3개 대화가 AI Context에 포함된다.
- [ ] AI 성공 응답만 DB에 저장된다.
- [ ] 사용자별 기록 조회와 삭제가 가능하다.
- [ ] AI Timeout, Retry, Rate Limit 오류가 처리된다.
- [ ] 핵심 이벤트가 `request_id`로 추적된다.
- [ ] 전체 자동 테스트가 통과한다.
- [ ] Railway 배포 URL의 `/health`가 200을 반환한다.
- [ ] Frontend와 배포 환경에서 전체 사용자 흐름이 동작한다.
- [ ] 세 팀원의 Issue, Commit, PR, Review 기록이 명확히 남아 있다.

---

## 18. 첫 작업 목록

아래 순서대로 Issue를 만들고 시작한다.

1. `[COMMON] API 계약 확정`
2. `[A/박주영] API 전용 FastAPI Scaffold 생성`
3. `[B/김승우] SQLAlchemy Database와 Model 구성`
4. `[C/반가희] Async OpenAI Service 기본 구현`
5. `[A/박주영] 회원가입 API 구현`
6. `[A/박주영] 로그인 및 JWT 인증 구현`
7. `[B/김승우] Chat Repository와 Service 구현`
8. `[C/반가희] AI Timeout, Retry, Error Mapping 구현`
9. `[B/김승우] Chat 생성·조회·삭제 API 구현`
10. `[C/반가희] CI와 Health Check 구성`
11. `[COMMON] 인증부터 ChatLog 삭제까지 통합 테스트`
12. `[COMMON] Railway 배포 및 Frontend 연결 검증`

첫 번째 Scaffold PR이 병합되기 전에는 기능 파일을 각자 생성하지 않는다. Scaffold 병합 후 최신 `main`에서 각 기능 브랜치를 새로 만들어 병렬 개발을 시작한다.
