from fastapi import FastAPI
from sqlalchemy.orm import Session

from database import engine, Base
from models import User, ChatLog


Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def hello():
    return {"message": "Hello World"}


def test_database():
    with Session(engine) as db:
        user = User(
            username="test_user",
            hashed_password="test_password",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print("저장된 사용자:", user.id, user.username)

@app.post("/test-user")
def create_test_user():
    with Session(engine) as db:
        user = User(
            username="test_user_2",
            hashed_password="test_password",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return {
            "id": user.id,
            "username": user.username,
        }

if __name__ == "__main__":
    test_database()