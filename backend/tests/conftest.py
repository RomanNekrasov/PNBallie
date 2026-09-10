import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client_factory(db_engine, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_APP_ORIGIN", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_ALLOW_REGISTRATION", "true")
    for name in ("OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)

    def test_session():
        with Session(db_engine) as session:
            yield session

    clients = []
    app.dependency_overrides[get_session] = test_session

    def factory():
        client = TestClient(app)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def client(client_factory):
    return client_factory()


@pytest.fixture
def registered(client_factory):
    def factory(email="admin@example.org", display_name="Admin"):
        client = client_factory()
        response = client.post("/api/auth/register", json={"email": email, "display_name": display_name, "password": "a-long-test-password"})
        assert response.status_code == 201, response.text
        info = response.json()
        client.headers["X-CSRF-Token"] = info["csrf_token"]
        return client, info["user"]
    return factory
