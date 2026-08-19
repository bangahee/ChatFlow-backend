import time
import logging
from openai import OpenAI, APIError, APITimeoutError
from sqlalchemy.orm import Session

from chatlog_repository import create_chatlog, get_recent_chatlogs

logger = logging.getLogger("chat_service")

client = OpenAI() # OPENAI_API_KEY 환경변수 자동으로 읽음(환경변수 env 설정 필요)

MAX_RETRIES = 3
TIMOUT_SECONDS = 10

def build_context(db: Session, user_id: int, current_question: str) -> list[dict]:
    # 최근 3개 대화와 현재 질문을 OpenAI 메시지 형식으로 재구성
    recent_logs = get_recent_chatlogs(db, user_id, limit=3)
    recent_logs = list(reversed(recent_logs))

    messages = [{"role": "system", "content": "당신은 친절한 AI 챗봇입니다."}]
    for log in recent_logs:
        messages.append({"role": "user", "content": log.question})
        messages.append({"role": "assistant", "content": log.answer})
    messages.append({"role": "user", "content": current_question})

    return messages

def call_openai_with_retry(messages: list[dict], request_id: str) -> str:
    # Timeout, 최대 3회 Retry, Exponential Backoff 적용
    logger.info(f"ai_call_start request_id={request_id}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            start = time.time()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                timeout=TIMOUT_SECONDS,
            )
            latency_ms = int((time.time() - start) * 1000)
            logger.info(
                f"ai_call_success request_id={request_id} latency_ms={latency_ms}"
            )
            return response.choices[0].message.content

        except (APITimeoutError, APIError) as e:
            logger.warning(
                f"ai_call_failure request_id={request_id} attempt={attempt} error={e}"
            )
            if attempt == MAX_RETRIES:
                raise
            wait_time = 2 ** (attempt - 1) # Exponential Backoff: 1회 실패 시 1초, 2회 실패 시 2초, 3회 실패 시 4초 ... 대기
            time.sleep(wait_time)

    raise RuntimeError("AI 호출이 예기치 않게 종료되었습니다.")

def process_chat(db: Session, user_id: int, question: str, request_id: str) -> str:
    # 전체 프로세스: Context 구성 -> AI 호출 -> DB 저장 -> 답변 반환
    messages = build_context(db, user_id, question)

    try:
        answer = call_openai_with_retry(messages, request_id)
    except (APITimeoutError, APIError):
        return "현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요."

    try:
        create_chatlog(db, user_id, question, answer)
        logger.info(f"db_save_success request_id={request_id} user_id={user_id}")
    except Exception as e:
        logger.error(f"db_save_failure request_id={request_id} error={e}")

    return answer
    
