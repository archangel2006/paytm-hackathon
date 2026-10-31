from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from server.settings import settings
from server.db.models import Base

connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
_request_session: ContextVar[Session | None] = ContextVar("request_session", default=None)


@contextmanager
def bind_session(db: Session) -> Generator[Session, None, None]:
    token = _request_session.set(db)
    try:
        yield db
    finally:
        _request_session.reset(token)


def current_session() -> Session:
    db = _request_session.get()
    if db is None:
        raise RuntimeError("No database session is bound to the current operation.")
    return db

def init_db(target_engine=None) -> None:
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
