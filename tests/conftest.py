import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", "postgresql://rag:rag@localhost:5432/rag_test")

from src.models import Base

TEST_DATABASE_URL = "postgresql://rag:rag@localhost:5432/rag_test"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL)
    with eng.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        s.begin_nested()
        yield s
        s.rollback()
