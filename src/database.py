import os
from collections.abc import Generator
from functools import cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


@cache
def _get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Example: postgresql://user:password@localhost:5432/dbname"
        )
    return create_engine(url)


def get_db() -> Generator[Session, None, None]:
    db = sessionmaker(bind=_get_engine())()
    try:
        yield db
    finally:
        db.close()
