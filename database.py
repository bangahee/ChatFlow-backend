from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite 파일 위치
SQLALCHEMY_DATABASE_URL = "sqlite:///./chatbot.db"

# DB와 연결하는 엔진 생성
# 엔진이란? DB파일과의 연결 통로
# SQLite는 기본적으로 멀티스레드 접근 차단
# 따라서 FALSE 옵션 부여로 비동기 요청 환경에서도 사용가능하도록 함
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=("check_same_thread": False)
)

# DB 세션 생성
# 요청마다 세션 하나를 새롭게 생성
# SessionLocal: 매 요청마다 DB 대화 창구를 새로 여는 역할
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 기본 클래스
# models.py의 User, ChatLog 클래스가 Base를 상속받아서 테이블로 인식되도록 함
Base = declarative_base()

# Router에서 Depends(get_db)로 부르면 매 요청마다 전용 DB 세션 생성
def get_db():
    db = SessionLocal()
    # 요청이 시작되면 세션을 열고, 함수 실행 도중에 해당 세션을 유지(yield)
    try:
        yield db
    # 요청이 끝나면 성공/에러 여부와 무관하게 세션 종료
    finally:
        db.close()
