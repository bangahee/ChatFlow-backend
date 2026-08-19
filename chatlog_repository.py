from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import ChatLog

def create_chatlog(db: Session, user_id: int, question: str, answer: str) -> ChatLog:
    new_log = ChatLog(user_id=user_id, question=question, answer=answer)
    db.add(new_log)
    try:
        db.commit()
        db.refresh(new_log)
    except Exception:
        db.rollback()
        raise
    return new_log

def get_recent_chatlogs(db: Session, user_id: int, limit: int = 3) -> list[ChatLog]:
    return (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user_id)
        .order_by(desc(ChatLog.created_at))
        .limit(limit)
        .all()
    )

def get_all_chatlogs(db: Session, user_id: int) -> list[ChatLog]:
    return (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user_id)
        .order_by(desc(ChatLog.created_at))
        .all()
    )

def delete_all_chatlogs(db: Session, user_id: int) -> None:
    try:
        db.query(ChatLog).filter(ChatLog.user_id == user_id).delete()
        db.commit()
    except Exception:
        db.rollback()
        raise
    