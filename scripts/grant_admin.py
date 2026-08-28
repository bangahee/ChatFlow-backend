"""Grant the persisted administrator role to one existing ChatFlow user."""

import argparse
import sys

from sqlalchemy import select

from app.config import get_settings
from app.database import create_db_engine, create_schema, create_session_factory
from app.models import User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Grant administrator access to an existing ChatFlow user."
    )
    parser.add_argument("username", help="Existing username to promote")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    engine = create_db_engine(settings.database_url)

    try:
        create_schema(engine)
        session_factory = create_session_factory(engine)
        with session_factory() as db:
            user = db.scalar(select(User).where(User.username == args.username))
            if user is None:
                print(
                    f"사용자를 찾을 수 없습니다: {args.username}",
                    file=sys.stderr,
                )
                return 1

            if not user.is_admin:
                user.is_admin = True
                db.commit()

        print(f"관리자 권한이 부여되었습니다: {args.username}")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
