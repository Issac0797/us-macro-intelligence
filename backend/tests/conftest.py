import os
import uuid

# Test-only default. Runtime stays PostgreSQL; no implicit application fallback.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ['MONITOR_ENABLED']='false'

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base
from app.sync import seed_catalog


@pytest.fixture(params=["sqlite", "postgres"] if os.getenv("TEST_DATABASE_URL") else ["sqlite"])
def db(request):
    schema = None
    if request.param == "postgres":
        engine = create_engine(os.environ["TEST_DATABASE_URL"])
        schema = "test_" + uuid.uuid4().hex
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        test_engine = engine.execution_options(schema_translate_map={None: schema})
    else:
        engine = test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(test_engine)
    with Session(test_engine, expire_on_commit=False) as session:
        seed_catalog(session)
        yield session
    if schema:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
