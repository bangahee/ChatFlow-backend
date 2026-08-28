# ChatFlow Backend A–Z 사용 가이드

이 문서는 팀원이 저장소를 내려받는 단계부터 로컬 실행, Swagger 테스트,
Frontend 연동, 자동 테스트와 배포 구조 확인까지 전체 Backend 사용 흐름을
진행할 수 있도록 작성한 가이드다.

코드를 수정하기 전에 먼저 이 문서의 **1~10단계**를 순서대로 실행해 현재
Backend가 어떻게 동작하는지 확인한다. 과제 필수요건에 없는 API 또는 DB 구조
변경은 바로 구현하지 말고 먼저 GitHub Issue와 팀 합의를 거친다.

## 0. 먼저 알아야 할 현재 상태

- Backend Framework: FastAPI
- Python: 3.13
- Database: SQLAlchemy + SQLite
- 인증: JWT Bearer Token
- AI: OpenAI Responses API
- 로컬 API 주소: `http://localhost:8000`
- API 문서: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`
- 배포 대상: Railway
- 통합 브랜치: `develop`
- 운영 브랜치: `main`
- 현재 전체 테스트: 110개

주요 사용자 흐름은 다음과 같다.

```text
회원가입
  → 로그인 및 JWT 발급
  → JWT로 현재 사용자 확인
  → 질문 전송
  → OpenAI 응답 생성
  → 질문과 응답을 SQLite에 저장
  → 내 기록 조회 또는 전체 삭제
```

## 1. 필요한 프로그램 설치

먼저 다음 프로그램이 필요하다.

- Git
- Python 3.13
- 코드 편집기(VS Code 등)
- 선택 사항: curl, Postman

터미널에서 설치 여부를 확인한다.

```bash
git --version
python3 --version
```

Python 결과가 `Python 3.13.x`인지 확인한다. macOS/Linux에서는 이 문서의
`python3` 명령을 사용한다. Windows PowerShell에서는 환경에 따라 `python` 또는
`py -3.13`을 사용한다.

## 2. 저장소 내려받기

저장소가 컴퓨터에 없다면 다음 명령을 실행한다.

```bash
git clone https://github.com/bangahee/ChatFlow-backend.git
cd ChatFlow-backend
git switch develop
git pull --ff-only origin develop
```

이미 저장소가 있다면 다음 명령부터 실행한다.

```bash
cd ChatFlow-backend
git status
git switch develop
git pull --ff-only origin develop
```

`git status`에 본인이 작성하지 않은 변경이 있으면 삭제하거나 덮어쓰지 말고 먼저
팀원에게 확인한다.

## 3. Python 가상환경과 패키지 설치

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

가상환경이 활성화되면 터미널 앞부분에 보통 `(.venv)`가 표시된다. 새 터미널을
열 때마다 다시 활성화해야 한다.

설치된 주요 패키지는 다음과 같다.

| 패키지 | 역할 |
|---|---|
| FastAPI/Uvicorn | API 서버와 로컬 실행 |
| SQLAlchemy | DB 모델과 쿼리 |
| PyJWT | Access Token 발급과 검증 |
| pwdlib/Argon2 | 비밀번호 해시 |
| OpenAI SDK | AI Responses API 호출 |
| pytest | 자동 테스트 |

## 4. 로컬 환경변수 설정

예제 파일을 복사해 로컬 전용 `.env`를 만든다.

### macOS/Linux

```bash
cp .env.example .env
```

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

`.env`의 기본 형태는 다음과 같다.

```dotenv
APP_ENV=development
LOG_LEVEL=INFO
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./chatflow.db
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-nano
OPENAI_TIMEOUT_SECONDS=20
OPENAI_MAX_RETRIES=3
CORS_ORIGINS=http://localhost:5173
```

### 실제 AI 응답이 필요한 경우

본인의 OpenAI Key를 `.env`의 `OPENAI_API_KEY`에만 넣는다.

```dotenv
OPENAI_API_KEY=<본인의 실제 Key>
```

다음 값은 절대 GitHub, 단체 채팅, Issue, PR, 로그 또는 화면 캡처에 노출하지
않는다.

- `.env` 전체 내용
- `OPENAI_API_KEY`
- Production `SECRET_KEY`
- 로그인 비밀번호
- JWT Access Token

OpenAI Key가 비어 있어도 서버 실행, 회원가입, 로그인, 기록 조회와 전체 pytest는
가능하다. Key가 없는 환경에서만 실제 `POST /api/chat` 요청은 503을 반환한다.
Production은 Railway의 서버 전용 Key로 실제 Responses API를 호출하며, 자동
테스트는 Mock AI를 사용하므로 실제 Key가 필요 없다.

## 5. Backend 서버 실행

가상환경이 활성화된 터미널에서 실행한다.

```bash
uvicorn app.main:app --reload
```

정상 실행 시 대략 다음 주소가 출력된다.

```text
Uvicorn running on http://127.0.0.1:8000
```

서버가 실행 중인 터미널은 그대로 두고, API 확인용으로 새 터미널 또는 브라우저를
사용한다. 서버 종료는 실행 중인 터미널에서 `Ctrl+C`를 누른다.

처음 실행하면 저장소 루트에 개발용 `chatflow.db`가 생성된다. 서버 시작 시 빈
DB라면 `users`, `chat_logs` 테이블을 자동 생성한다.

## 6. 서버가 살아 있는지 확인

브라우저에서 다음 주소를 연다.

```text
http://localhost:8000/health
```

또는 새 터미널에서 실행한다.

```bash
curl -i http://localhost:8000/health
```

정상 결과:

```text
HTTP/1.1 200 OK
```

```json
{"status":"ok"}
```

응답 Header에는 요청 추적용 `X-Request-ID`도 포함된다.

## 7. Swagger에서 전체 사용자 흐름 테스트

브라우저에서 다음 주소를 연다.

```text
http://localhost:8000/docs
```

Swagger에서는 각 API를 펼친 뒤 `Try it out` → 요청 입력 → `Execute` 순서로
실행한다.

### 7-1. 회원가입

`POST /api/auth/register`를 실행한다.

```json
{
  "username": "test_user",
  "password": "password123"
}
```

입력 규칙:

- 아이디: 3~50자의 영문, 숫자, 밑줄(_)
- 비밀번호 길이: 8~128자

정상 상태 코드는 `201`이다. 같은 아이디로 다시 가입하면 `400`이 발생한다.

### 7-2. 로그인과 JWT 복사

`POST /api/auth/login`을 실행한다.

```json
{
  "username": "test_user",
  "password": "password123"
}
```

정상 상태 코드는 `200`이며 다음 형태의 응답이 나온다.

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

`access_token` 값만 복사한다. 이 Token은 비밀번호처럼 외부에 공유하지 않는다.

### 7-3. Swagger 인증

Swagger 화면 오른쪽 위 `Authorize` 버튼을 누른다.

1. Bearer 인증 입력란에 복사한 `access_token` 값만 붙여 넣는다.
2. `Authorize`를 누른다.
3. 창을 닫는다.

Swagger가 요청 시 `Authorization: Bearer <token>` Header를 자동으로 추가한다.

### 7-4. 현재 사용자 확인

`GET /api/me`를 실행한다.

정상 상태 코드는 `200`이며 로그인한 사용자 정보가 반환된다. `401`이면 Token을
다시 발급받아 `Authorize`한다.

### 7-5. AI 질문 전송

`POST /api/chat`을 실행한다.

```json
{
  "question": "FastAPI가 무엇인지 한 문장으로 설명해 줘"
}
```

질문은 공백 제외 1~500자다. 정상 상태 코드는 `201`이며 다음 값이 반환된다.

- `id`: 저장된 Chat ID
- `question`: 사용자 질문
- `response`: AI 답변
- `created_at`: UTC 생성 시각
- `request_id`: 로그 추적 ID

실제 AI 호출을 하려면 `.env`에 유효한 `OPENAI_API_KEY`가 필요하다.

### 7-6. 내 Chat 기록 조회

`GET /api/me/chats`를 실행한다.

```json
{
  "items": [
    {
      "id": 1,
      "question": "질문",
      "response": "AI 답변",
      "created_at": "UTC 시각"
    }
  ],
  "count": 1
}
```

다른 사용자의 기록은 조회되지 않는다.

### 7-7. 내 Chat 기록 전체 삭제

`DELETE /api/me/chats`를 실행한다.

이 API는 특정 Chat 하나가 아니라 현재 사용자의 기록 전체를 삭제한다. 삭제 후
`GET /api/me/chats`를 다시 실행하면 `count`가 `0`인지 확인할 수 있다.

## 8. curl로 같은 흐름 테스트

Swagger 대신 터미널에서 테스트하려면 다음 예시를 사용한다.

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"curl_user","password":"password123"}'
```

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"curl_user","password":"password123"}'
```

로그인 응답의 Token을 복사한 뒤 `<jwt>`를 교체한다.

```bash
curl http://localhost:8000/api/me \
  -H 'Authorization: Bearer <jwt>'
```

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <jwt>' \
  -d '{"question":"안녕하세요"}'
```

```bash
curl http://localhost:8000/api/me/chats \
  -H 'Authorization: Bearer <jwt>'
```

```bash
curl -X DELETE http://localhost:8000/api/me/chats \
  -H 'Authorization: Bearer <jwt>'
```

## 9. Frontend에서 Backend 연결하기

Frontend가 사용하는 Backend Base URL은 로컬에서 다음과 같다.

```text
http://localhost:8000
```

Frontend `.env` 예시:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

Backend `.env`의 `CORS_ORIGINS`에는 Frontend가 실제로 열리는 Origin을 넣는다.

```dotenv
CORS_ORIGINS=http://localhost:5173
```

포트가 다르면 실제 Frontend 주소에 맞춘다. 여러 주소를 허용하려면 쉼표로
구분한다.

```dotenv
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
```

`.env`를 수정한 뒤에는 Backend 서버를 재시작한다.

### Frontend가 사용하는 API 계약

| 기능 | Method | 경로 | 인증 | 요청 Body |
|---|---|---|---|---|
| 회원가입 | POST | `/api/auth/register` | X | `username`, `password` |
| 로그인 | POST | `/api/auth/login` | X | `username`, `password` |
| 사용자 복원 | GET | `/api/me` | Bearer | 없음 |
| 질문 전송 | POST | `/api/chat` | Bearer | `question` |
| 기록 조회 | GET | `/api/me/chats` | Bearer | 없음 |
| 기록 전체 삭제 | DELETE | `/api/me/chats` | Bearer | 없음 |

보호 API에는 반드시 다음 Header를 보낸다.

```text
Authorization: Bearer <access_token>
```

### 현재 API로 구현할 수 있는 사이드바

`GET /api/me/chats`의 `items`를 사용하면 Backend 변경 없이 다음 기능을 만들 수
있다.

- 과거 질문 목록 표시
- 질문 일부를 사이드바 제목처럼 표시
- 작성 시간 표시
- 선택한 질문과 답변 표시
- 새 Chat 입력 화면으로 이동
- 전체 기록 삭제

현재 DB는 각 질문/응답을 독립된 `ChatLog`로 저장한다. 다음 기능은 아직 API에
없으며 사전 팀 합의 없이 Frontend에서 임의로 가정하면 안 된다.

- 여러 메시지를 하나의 Conversation으로 그룹화
- 대화방 제목 저장 또는 수정
- 특정 기록 하나만 삭제
- Conversation별 목록/상세 조회
- 서버에 새 대화방 상태 저장

이 기능들이 정말 필요하면 Backend 수정 전에 Issue에 사용자 흐름, 필요한 API,
DB 변경, 기존 테스트 영향과 담당자를 작성한다.

## 10. 자동 테스트 실행

서버를 별도로 실행하지 않아도 된다. 가상환경에서 다음 명령을 실행한다.

```bash
python -m pytest -q
```

정상 기준:

```text
110 passed
```

테스트는 임시 SQLite DB와 Mock OpenAI Client를 사용하므로 실제 OpenAI Key와
운영 DB가 필요 없다.

특정 파일만 실행할 수도 있다.

```bash
python -m pytest -q tests/test_auth_api.py
python -m pytest -q tests/test_chat_api.py
python -m pytest -q tests/test_ai_service.py
python -m pytest -q tests/test_backend_flow.py
```

코드를 수정했다면 PR을 만들기 전에 반드시 전체 테스트를 다시 실행한다.

## 11. 프로젝트 폴더 구조 이해하기

```text
app/
├── main.py                 FastAPI 생성, Middleware, Router 등록
├── config.py               .env 및 Settings
├── database.py             Engine, Session, Schema 생성
├── dependencies.py         DB, 인증 사용자, AI 의존성
├── models.py               User, ChatLog 모델
├── observability.py        request_id와 구조화 로그
├── routers/
│   ├── auth.py             회원가입, 로그인, 현재 사용자 API
│   ├── chat.py             Chat 생성, 조회, 삭제 API
│   └── health.py           Health Check
├── schemas/                요청/응답 Pydantic Schema
├── repositories/           SQLAlchemy 조회 쿼리
└── services/               인증, Chat 흐름, OpenAI 로직

tests/                      pytest 테스트
.github/workflows/test.yml  GitHub Actions
railway.json                Railway 빌드/실행 설정
.env.example                환경변수 예시
requirements.txt            Python 의존성
```

요청 처리 순서:

```text
Frontend/Swagger
  → Router: HTTP 입력과 상태 코드
  → Dependency: JWT 사용자와 DB Session 확인
  → Service: 업무 흐름과 commit/rollback
  → Repository: SQLAlchemy 쿼리
  → SQLite
```

Chat 요청은 Service에서 최근 Chat 최대 3개를 가져와 OpenAI Context에 추가한 후
AI 응답이 성공한 경우에만 DB에 저장한다.

## 12. 로그 읽는 방법

서버 터미널에는 한 요청의 이벤트가 JSON 한 줄씩 출력된다. 같은 요청은 동일한
`request_id`를 공유한다.

성공적인 Chat 흐름:

```text
request_received
ai_call_started
ai_call_succeeded
db_save_succeeded
request_completed
```

인증 실패:

```text
request_received
auth_failed
request_completed
```

로그에는 길이, 상태 코드, latency와 오류 종류만 기록하며 비밀번호, JWT, 질문과
응답 본문, OpenAI Key를 기록하지 않는다.

문제가 발생하면 API 응답의 `X-Request-ID` 또는 Chat 응답의 `request_id`를 기준으로
로그를 찾는다.

## 13. 자주 발생하는 오류

### `command not found: uvicorn`

가상환경을 활성화하고 패키지를 다시 설치한다.

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### `Address already in use`

8000번 포트를 다른 프로그램이 사용 중이다. 기존 Backend 서버를 종료하거나 임시로
다른 포트를 사용한다.

```bash
uvicorn app.main:app --reload --port 8001
```

이 경우 Swagger와 Frontend Base URL도 `http://localhost:8001`로 변경한다.

### 401 Unauthorized

- 로그인을 먼저 했는지 확인한다.
- `Bearer`와 Token 사이에 공백이 있는지 확인한다.
- Token이 만료되었으면 다시 로그인한다.
- 다른 `SECRET_KEY`로 서버를 재시작했다면 기존 Token을 다시 사용할 수 없다.

### 422 Unprocessable Entity

- 아이디가 3~50자의 영문, 숫자, 밑줄(_)인지 확인한다.
- 비밀번호가 8자 이상인지 확인한다.
- 질문이 공백이 아니고 500자 이하인지 확인한다.
- 요청 JSON에 정의되지 않은 추가 필드가 없는지 확인한다.

### Chat 요청이 503

- `.env`에 `OPENAI_API_KEY`가 설정되었는지 확인한다.
- Key의 quota/billing 상태를 확인한다.
- `.env` 수정 후 서버를 재시작했는지 확인한다.

### 브라우저에서 CORS 오류

- Backend `.env`의 `CORS_ORIGINS`가 브라우저 주소와 정확히 같은지 확인한다.
- `http`와 `https`, Domain, 포트가 모두 일치해야 한다.
- 여러 Origin은 쉼표로 구분한다.
- `.env` 수정 후 Backend를 재시작한다.

### 기록이 보이지 않음

- 기록을 만든 사용자와 현재 로그인 사용자가 같은지 확인한다.
- `GET /api/me`로 현재 사용자를 먼저 확인한다.
- `DATABASE_URL`이 이전 실행과 같은 DB 파일을 가리키는지 확인한다.

## 14. Git 작업 방법

`main` 또는 `develop`에 직접 작업하거나 직접 Push하지 않는다.

```bash
git switch develop
git pull --ff-only origin develop
git switch -c <종류>/<짧은-작업명>
```

브랜치 예시:

```text
feat/chat-sidebar-support
fix/auth-error-message
test/chat-history
docs/backend-usage
```

작업 후:

```bash
python -m pytest -q
git status
git add <변경한 파일>
git commit -m "type(scope): 변경 내용"
git push -u origin <브랜치명>
```

그다음 GitHub에서 해당 브랜치를 `develop`로 보내는 PR을 만든다.

```text
작업 브랜치 → PR/리뷰/CI → develop → 최종 Release PR → main
```

PR에는 작업 내용, 테스트 결과와 API/DB 변경 여부를 작성한다. API나 DB 변경은
Frontend에도 영향을 주므로 구현 전에 팀 합의를 받는다.

## 15. Railway 배포 흐름

일반 Frontend 작업자는 Production Secret이나 Railway 설정을 변경할 필요가 없다.
배포 담당자가 다음 순서로 진행한다.

1. GitHub Backend `main`을 Railway Service에 연결한다.
2. `railway.json`의 Railpack/Uvicorn 설정으로 배포한다.
3. Railway Volume을 Backend Service의 `/data`에 Mount한다.
4. Production 환경 변수를 Railway Variables에 등록한다.
5. Public Domain을 생성한다.
6. `/health`가 200인지 확인한다.
7. 회원가입 → 로그인 → 실제 Chat → 기록 조회를 검증한다.
8. Backend를 재시작하고 같은 Chat ID가 유지되는지 확인한다.

필수 Production 값:

```dotenv
APP_ENV=production
LOG_LEVEL=INFO
SECRET_KEY=<충분히 긴 임의 문자열>
OPENAI_API_KEY=<server-side key>
OPENAI_MODEL=gpt-5-nano
OPENAI_TIMEOUT_SECONDS=20
OPENAI_MAX_RETRIES=3
CORS_ORIGINS=https://chat-flow-topaz.vercel.app
DATABASE_URL=sqlite:////data/chatflow.db
```

Volume Mount 경로 `/data`와 `DATABASE_URL`의 `/data/chatflow.db`가 반드시
일치해야 한다. 더 자세한 검증 절차는
[Railway 배포 검증 문서](RAILWAY_DEPLOYMENT.md)를 따른다.

## 16. 완료 체크리스트

Backend 사용 전 다음 항목을 직접 확인한다.

- [ ] `develop` 최신 코드를 받았다.
- [ ] Python 가상환경을 만들고 의존성을 설치했다.
- [ ] `.env`를 만들었고 Secret을 Git에 올리지 않았다.
- [ ] Uvicorn 서버가 실행된다.
- [ ] `/health`가 200을 반환한다.
- [ ] Swagger에서 회원가입과 로그인을 했다.
- [ ] JWT로 `/api/me`를 호출했다.
- [ ] 실제 또는 Mock 환경에서 Chat 흐름을 이해했다.
- [ ] `/api/me/chats` 응답 구조를 확인했다.
- [ ] 현재 Sidebar로 가능한 기능과 불가능한 기능을 구분했다.
- [ ] 전체 pytest가 통과한다.
- [ ] 변경 작업은 별도 브랜치와 PR로 진행한다.

위 체크리스트를 완료한 다음에 기능 변경안을 제안하면 현재 Backend 계약과 실제
영향을 기준으로 팀원들과 논의할 수 있다.
