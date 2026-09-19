"""Tests for registration, login, session cookie, and password storage."""

import os
import sys

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("pwdlib")
pytest.importorskip("jwt")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.v1.endpoints import auth as auth_api  # noqa: E402
from app.db import models  # noqa: E402
from app.db.session import Base, get_db  # noqa: E402


@pytest.fixture()
def client_and_db(monkeypatch):
    monkeypatch.setattr(auth_api.settings, "auth_enabled", True)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(auth_api.router, prefix="/api/v1/auth")
    app.dependency_overrides[get_db] = _override_db
    auth_api.reset_login_throttle()
    yield TestClient(app), TestingSession
    auth_api.reset_login_throttle()


def _register(client, username="Alice", password="correct horse"):
    return client.post("/api/v1/auth/register", json={"username": username, "password": password})


def test_register_sets_session_and_me_returns_user(client_and_db):
    client, _ = client_and_db
    response = _register(client)
    assert response.status_code == 201
    assert response.json()["username"] == "alice"
    assert auth_api.SESSION_COOKIE in response.cookies

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_password_is_stored_as_argon2_hash(client_and_db):
    client, Session = client_and_db
    _register(client, password="correct horse")
    with Session() as db:
        user = db.scalar(select(models.User))
    assert user.password_hash.startswith("$argon2id$")
    assert "correct horse" not in user.password_hash


def test_duplicate_username_is_case_insensitive(client_and_db):
    client, _ = client_and_db
    assert _register(client, username="alice").status_code == 201
    assert _register(client, username="ALICE").status_code == 409


def test_login_logout_flow(client_and_db):
    client, _ = client_and_db
    _register(client)
    client.post("/api/v1/auth/logout")
    client.cookies.clear()
    assert client.get("/api/v1/auth/me").status_code == 401

    response = client.post(
        "/api/v1/auth/login", json={"username": "ALICE", "password": "correct horse"}
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


def test_wrong_password_and_unknown_user_share_error(client_and_db):
    client, _ = client_and_db
    _register(client)
    wrong = client.post("/api/v1/auth/login", json={"username": "alice", "password": "nope-nope"})
    unknown = client.post("/api/v1/auth/login", json={"username": "bob", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_register_validation(client_and_db):
    client, _ = client_and_db
    assert _register(client, username="a b").status_code == 422
    assert _register(client, password="short").status_code == 422


def test_tampered_session_cookie_is_rejected(client_and_db):
    client, _ = client_and_db
    _register(client)
    client.cookies.set(auth_api.SESSION_COOKIE, "not-a-valid-token")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_failed_logins_are_throttled(client_and_db):
    client, _ = client_and_db
    _register(client)
    body = {"username": "alice", "password": "wrong-password"}
    codes = [client.post("/api/v1/auth/login", json=body).status_code
             for _ in range(auth_api.MAX_FAILED_LOGINS + 1)]
    assert codes[:-1] == [401] * auth_api.MAX_FAILED_LOGINS
    assert codes[-1] == 429
    # Even the right password is blocked while throttled.
    ok_body = {"username": "alice", "password": "correct horse"}
    assert client.post("/api/v1/auth/login", json=ok_body).status_code == 429


def test_google_login_creates_then_reuses_account(client_and_db, monkeypatch):
    client, Session = client_and_db
    monkeypatch.setattr(auth_api.settings, "google_oauth_client_id", "client-123.apps.googleusercontent.com")
    claims = {"sub": "google-sub-1", "email": "Jane.Doe@gmail.com", "email_verified": True, "name": "Jane"}
    monkeypatch.setattr(auth_api, "verify_google_credential", lambda credential: claims)

    first = client.post("/api/v1/auth/google", json={"credential": "x" * 40})
    assert first.status_code == 200
    assert first.json()["username"] == "jane.doe"
    assert client.get("/api/v1/auth/me").json()["email"] == "Jane.Doe@gmail.com"

    client.cookies.clear()
    second = client.post("/api/v1/auth/google", json={"credential": "x" * 40})
    assert second.json()["id"] == first.json()["id"]

    with Session() as db:
        user = db.scalar(select(models.User))
    assert user.password_hash is None
    # A Google-only account can't be logged into with a password.
    assert client.post("/api/v1/auth/login", json={"username": "jane.doe", "password": "anything1"}).status_code == 401


def test_google_login_username_collision_and_rejections(client_and_db, monkeypatch):
    client, _ = client_and_db
    _register(client, username="jane.doe")
    client.cookies.clear()
    monkeypatch.setattr(auth_api.settings, "google_oauth_client_id", "client-123")

    monkeypatch.setattr(auth_api, "verify_google_credential",
                        lambda c: {"sub": "s2", "email": "jane.doe@example.com", "email_verified": True})
    assert client.post("/api/v1/auth/google", json={"credential": "x" * 40}).json()["username"] == "jane.doe2"

    monkeypatch.setattr(auth_api, "verify_google_credential",
                        lambda c: {"sub": "s3", "email": "x@example.com", "email_verified": False})
    assert client.post("/api/v1/auth/google", json={"credential": "x" * 40}).status_code == 401

    def invalid(credential):
        raise ValueError("bad token")

    monkeypatch.setattr(auth_api, "verify_google_credential", invalid)
    assert client.post("/api/v1/auth/google", json={"credential": "x" * 40}).status_code == 401


def test_google_login_disabled_without_client_id(client_and_db, monkeypatch):
    client, _ = client_and_db
    monkeypatch.setattr(auth_api.settings, "google_oauth_client_id", "")
    assert client.get("/api/v1/auth/config").json() == {"auth_enabled": True, "google_client_id": None}
    assert client.post("/api/v1/auth/google", json={"credential": "x" * 40}).status_code == 404


def test_account_endpoints_are_off_by_default(client_and_db, monkeypatch):
    client, _ = client_and_db
    monkeypatch.setattr(auth_api.settings, "auth_enabled", False)
    assert client.get("/api/v1/auth/config").json() == {"auth_enabled": False, "google_client_id": None}
    assert _register(client).status_code == 404
    assert client.post("/api/v1/auth/login", json={"username": "a", "password": "b"}).status_code == 404
    assert client.get("/api/v1/auth/me").status_code == 404
