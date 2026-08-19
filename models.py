from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)

    # User 하나가 여러 ChatLog를 가짐 (1:N 관계)
    # back_populates는 양쪽(user<->chatlog)이 서로를 알 수 있게 짝지어주는 것
    chatlogs = relationship("ChatLog", back_populates="user")

class ChatLog(Base):
    __tablename__ = "chatlogs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ChatLog 하나는 User에 속함
    user = relationship("User", back_populates="chatlogs")