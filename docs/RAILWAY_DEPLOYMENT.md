# Railway 배포 및 데이터 영속성 검증

이 문서는 저장소 코드만으로 자동 수행할 수 없는 Railway 프로젝트 연결,
Production Secret 등록과 SQLite Volume 영속성 검증 절차를 정의한다.

## 1. Service와 Volume 설정

1. Railway에서 이 GitHub 저장소의 배포 대상 브랜치를 연결한다.
2. Persistent Volume을 생성해 Backend Service의 `/data`에 Mount한다.
3. 다음 환경 변수를 Railway Variables에 등록한다.

```dotenv
APP_ENV=production
LOG_LEVEL=INFO
SECRET_KEY=<충분히 긴 임의 문자열>
OPENAI_API_KEY=<OpenAI server-side key>
OPENAI_MODEL=gpt-5-nano
OPENAI_TIMEOUT_SECONDS=20
OPENAI_MAX_RETRIES=3
CORS_ORIGINS=https://chat-flow-topaz.vercel.app
DATABASE_URL=sqlite:////data/chatflow.db
```

실제 값은 저장소, PR, Issue, 로그 또는 화면 캡처에 노출하지 않는다.

`railway.json`에 정의된 배포 설정은 다음과 같다.

- Builder: `RAILPACK`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check: `/health`
- Health timeout: 100초
- Restart policy: `ON_FAILURE`

## 2. 배포 직후 확인

배포 URL을 `https://<backend-domain>`으로 바꾸어 확인한다.

```bash
curl -i https://<backend-domain>/health
```

필수 결과:

- HTTP 200
- Body `{"status":"ok"}`
- `X-Request-ID` 응답 Header
- Railway 로그에 같은 ID의 `request_received`, `request_completed`

## 3. 전체 Backend 흐름 확인

README의 요청 예시를 Production URL에서 순서대로 실행한다.

1. 회원가입 201
2. 로그인 200 및 JWT 수신
3. JWT로 Chat 요청 201
4. 실제 AI 응답과 `request_id` 수신
5. 기록 조회에서 방금 저장한 질문·응답 확인
6. Railway 로그에서 같은 `request_id`의 다음 이벤트 확인

```text
request_received
ai_call_started
ai_call_succeeded
db_save_succeeded
request_completed
```

API Key, JWT, 비밀번호, 질문과 AI 응답 본문이 로그에 없는지도 함께 확인한다.

## 4. SQLite Volume 영속성 확인

1. 삭제하지 않을 테스트 사용자를 만들고 Chat 기록을 1개 이상 저장한다.
2. `GET /api/me/chats`의 `count`와 Chat ID를 기록한다.
3. Railway에서 Backend Service를 재배포 또는 재시작한다.
4. `/health`가 다시 200이 될 때까지 기다린다.
5. 같은 계정으로 다시 로그인한다.
6. `GET /api/me/chats`를 호출한다.
7. 재시작 전 기록과 Chat ID가 그대로 존재하는지 확인한다.

기록이 사라지면 다음 항목을 확인한다.

- Volume Mount 경로가 `/data`인지
- `DATABASE_URL`이 `sqlite:////data/chatflow.db`인지
- Backend Service와 Volume이 같은 Railway Service에 연결되었는지
- 배포 로그에 다른 SQLite 경로가 사용되었다는 흔적이 없는지

## 5. Frontend 통합 확인

1. Railway `CORS_ORIGINS`를 실제 Vercel Production Origin과 정확히 일치시킨다.
2. Frontend `VITE_API_BASE_URL`을 Railway Backend URL로 설정한다.
3. Browser에서 회원가입 → 로그인 → 질문 → 기록 조회 → 삭제를 확인한다.
4. 허용되지 않은 Origin에서 CORS 요청이 거부되는지 확인한다.

## 6. 실제 검증 결과 (기능 2026-08-29, Release 상태 2026-09-01 KST)

| 항목 | 검증 결과 |
|---|---|
| Backend URL | `https://chatflow-backend-production-b90c.up.railway.app` |
| Frontend URL | `https://chat-flow-topaz.vercel.app` |
| Backend 확인 기준 Release | 2026-09-01 `main` 커밋 `655d87b`(PR #25), Railway 상태 `Successful` |
| Backend 기능 검증 기준 | 실행 코드 `e664343`(PR #23), Railway Deployment `8d4705df` |
| Frontend 확인 기준 Release | 2026-09-01 `main` 커밋 `64698da`(PR #23), Vercel `Ready` |
| Health | Railway 재시작 후 `200 {"status":"ok"}` |
| CORS | Frontend Origin Preflight `200`, 허용 Origin Header 일치 |
| 통합 흐름 | 회원가입 `201`, 로그인 `200`, 실제 Chat `201`, 기록 조회 성공 |
| 관리자 흐름 | 관리자 로그인, 사용자 목록·사용자별 대화 조회 `200` |
| 인증 복원 | Frontend 새로고침 후 인증과 기록 유지 |
| 운영 로그 | 동일 `request_id`로 요청·AI·DB 저장·완료 이벤트 연결 |
| Timeout/Retry | AI timeout 4회 시도 후 `504` 반환 |
| DB 영속성 | Railway Container 재시작 후 동일 Chat과 AI 응답 유지 |
| Frontend 오류 | Browser Console Error 없음 |

Railway GitHub App 권한과 `main` Source 연결을 복구하고 Auto Deploy를 활성화한 뒤,
실행 코드 `e664343`을 수동 배포해 전체 기능을 검증했다. 이후 문서 동기화 PR #25가
포함된 `655d87b`도 Railway에 성공적으로 배포됐다. PR #25는 실행 코드를 변경하지
않으므로 아래 운영 검증은 현재 Release에도 동일하게 적용된다. 성공한 Chat 요청
`0947aa18-f5dc-423f-b6f0-aa2e6371f90c`에서 아래 이벤트가 동일한 `request_id`를
공유하는 것을 확인했다. 질문·응답 본문과 Secret은 로그에 기록되지 않았다.

```text
request_received
ai_call_started
ai_call_succeeded
db_save_succeeded
request_completed
```

AI timeout 요청 `5fee20cf-26e2-46be-80a6-ffab470a3cdd`는 총 4회 시도 후 `504`로
완료됐다. Container 재시작 뒤 Health 요청
`9988c3aa-43db-47e1-8d31-c8c406b2cc9e`가 `200`으로 완료됐고, Frontend 새로고침
후에도 재시작 전 Chat과 AI 응답이 그대로 조회되어 `/data` Volume 영속성도
재확인했다.

## 7. 제출 증빙 기록

최종 README 또는 제출 문서에 다음을 기록한다.

| 항목 | 기록할 값 |
|---|---|
| Backend URL | `https://...` |
| Health 확인 시각 | UTC/KST 시각 |
| 배포 대상 commit | Git SHA |
| CI 결과 | GitHub Actions 링크 |
| DB 영속성 | 재시작 전·후 동일 Chat ID 확인 |
| Frontend URL | `https://...` |
| 통합 검증 | 회원가입→로그인→Chat→조회/삭제 성공 |

Secret과 사용자 입력 내용이 포함된 화면은 제출 증빙에서 마스킹한다.
