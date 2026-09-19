import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://docuquest:docuquest_dev_password@localhost:5432/docuquest")

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.environ["DATABASE_URL"].rsplit("/", 1)[0] + "/docuquest_test"

engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


@pytest.fixture(scope="session", autouse=True)
def _create_test_database():
    admin_engine = create_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT", future=True)
    with admin_engine.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'docuquest_test'")).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE docuquest_test"))
    admin_engine.dispose()

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        # Clean all tables between tests to keep them independent.
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture()
def client(db_session, tmp_path, monkeypatch):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    monkeypatch.setattr("app.services.storage.settings.STORAGE_ROOT", str(tmp_path))

    # Run Celery tasks synchronously and inline so tests don't need a live worker,
    # and point the task's own DB sessions at the same test database/engine.
    from app.workers.tasks import process_document

    monkeypatch.setattr("app.workers.tasks.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.api.routes.documents.process_document.delay", lambda doc_id: process_document.run(doc_id))

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "supersecret123"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
