import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from server.db.models import Base
from server.db.session import init_db
from server.db.repo import PlatformRepo
from server.adapters.clock import clock

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def test_repo(test_db):
    return PlatformRepo(test_db)

