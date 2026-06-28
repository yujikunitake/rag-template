from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.auth import create_access_token, create_refresh_token, hash_password
from src.database import get_db
from src.main import app
from src.models import User


@pytest.fixture
def test_user(session):
    user = User(
        email="test@example.com",
        hashed_password=hash_password("correct_password"),
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def client(session):
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_rate_limit():
    from src.auth import limiter

    limiter._limiter.storage.reset()
    yield


# --- Login ---


def test_auth_login_valid_returns_cookies(client, test_user):
    response = client.post(
        "/auth/login", json={"email": "test@example.com", "password": "correct_password"}
    )
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


def test_auth_login_wrong_password_returns_401(client, test_user):
    response = client.post("/auth/login", json={"email": "test@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


def test_auth_login_unknown_email_returns_401(client):
    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "any"})
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


def test_auth_login_rate_limit(client):
    for _ in range(5):
        client.post("/auth/login", json={"email": "nobody@example.com", "password": "any"})
    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "any"})
    assert response.status_code == 429


def test_auth_login_unknown_email_always_runs_verify_password(client):
    # verify_password must run even when user does not exist to prevent timing attacks
    with patch("src.auth.verify_password") as mock_verify:
        mock_verify.return_value = False
        client.post("/auth/login", json={"email": "nobody@example.com", "password": "any"})
        mock_verify.assert_called_once()


# --- Refresh ---


def test_auth_refresh_valid_returns_new_access_token(client, test_user):
    client.post("/auth/login", json={"email": "test@example.com", "password": "correct_password"})
    response = client.post("/auth/refresh")
    assert response.status_code == 200
    assert "access_token" in response.cookies


def test_auth_refresh_without_cookie_returns_401(client):
    response = client.post("/auth/refresh")
    assert response.status_code == 401


def test_auth_refresh_expired_token_returns_401(client, test_user):
    expired = create_refresh_token(str(test_user.id), expires_delta=timedelta(seconds=-1))
    client.cookies.set("refresh_token", expired)
    response = client.post("/auth/refresh")
    assert response.status_code == 401


# --- Logout ---


def test_auth_logout_clears_cookies(client, test_user):
    client.post("/auth/login", json={"email": "test@example.com", "password": "correct_password"})
    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert response.cookies.get("access_token", "") == ""
    assert response.cookies.get("refresh_token", "") == ""


# --- Cookies: secure and max_age ---


def test_auth_login_cookies_have_max_age(client, test_user):
    response = client.post(
        "/auth/login", json={"email": "test@example.com", "password": "correct_password"}
    )
    set_cookies = response.headers.get_list("set-cookie")
    access_cookie = next(c for c in set_cookies if "access_token=" in c)
    refresh_cookie = next(c for c in set_cookies if "refresh_token=" in c)
    assert "max-age=900" in access_cookie.lower()
    assert "max-age=604800" in refresh_cookie.lower()


def test_auth_cookies_are_secure_outside_development(client, test_user):
    with patch("src.auth.SECURE_COOKIES", True):
        response = client.post(
            "/auth/login", json={"email": "test@example.com", "password": "correct_password"}
        )
    set_cookies = response.headers.get_list("set-cookie")
    access_cookie = next(c for c in set_cookies if "access_token=" in c)
    assert "secure" in access_cookie.lower()


def test_auth_cookies_not_secure_in_development(client, test_user):
    with patch("src.auth.SECURE_COOKIES", False):
        response = client.post(
            "/auth/login", json={"email": "test@example.com", "password": "correct_password"}
        )
    set_cookies = response.headers.get_list("set-cookie")
    access_cookie = next(c for c in set_cookies if "access_token=" in c)
    assert "secure" not in access_cookie.lower()


# --- Protected route ---


def test_protected_route_without_token_returns_401(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_protected_route_with_valid_token_returns_200(client, test_user):
    client.post("/auth/login", json={"email": "test@example.com", "password": "correct_password"})
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_protected_route_with_expired_token_returns_401(client, test_user):
    expired = create_access_token(str(test_user.id), expires_delta=timedelta(seconds=-1))
    client.cookies.set("access_token", expired)
    response = client.get("/auth/me")
    assert response.status_code == 401


# --- Access vs refresh token distinction ---


def test_auth_refresh_rejects_access_token(client, test_user):
    access = create_access_token(str(test_user.id))
    client.cookies.set("refresh_token", access)
    response = client.post("/auth/refresh")
    assert response.status_code == 401


def test_protected_route_rejects_refresh_token(client, test_user):
    refresh = create_refresh_token(str(test_user.id))
    client.cookies.set("access_token", refresh)
    response = client.get("/auth/me")
    assert response.status_code == 401
