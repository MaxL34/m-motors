from unittest.mock import patch

import pytest

from app.models.user import User
from app.utils.security import create_access_token, hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(db, *, email, password="password123", phone_number=None, is_active=True):
    user = User(
        first_name="Jean", last_name="Dupont", email=email,
        phone_number=phone_number,
        password_hash=hash_password(password),
        is_active=is_active, is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_cookie(user_id: int) -> str:
    return create_access_token({"sub": str(int(user_id)), "is_admin": False})


# ── POST /profile — unicité du téléphone ─────────────────────────────────────

class TestProfilePhoneUniqueness:

    def test_duplicate_phone_returns_422(self, client, db):
        make_user(db, email="user1@example.com", phone_number="0600000001")
        user2 = make_user(db, email="user2@example.com", phone_number="0600000002")
        client.cookies.set("access_token", auth_cookie(user2.id))
        response = client.post("/profile", data={
            "first_name": "Jean", "last_name": "Dupont",
            "email": "user2@example.com",
            "phone_number": "0600000001",
        })
        assert response.status_code == 422

    def test_duplicate_phone_shows_error(self, client, db):
        make_user(db, email="user1@example.com", phone_number="0600000001")
        user2 = make_user(db, email="user2@example.com", phone_number="0600000002")
        client.cookies.set("access_token", auth_cookie(user2.id))
        response = client.post("/profile", data={
            "first_name": "Jean", "last_name": "Dupont",
            "email": "user2@example.com",
            "phone_number": "0600000001",
        })
        assert "téléphone" in response.text.lower()

    def test_keeping_own_phone_is_allowed(self, client, db):
        user = make_user(db, email="user@example.com", phone_number="0600000001")
        client.cookies.set("access_token", auth_cookie(user.id))
        response = client.post("/profile", data={
            "first_name": "Jean", "last_name": "Dupont",
            "email": "user@example.com",
            "phone_number": "0600000001",
        }, follow_redirects=False)
        assert response.status_code == 200

    def test_new_unique_phone_is_accepted(self, client, db):
        user = make_user(db, email="user@example.com", phone_number="0600000001")
        client.cookies.set("access_token", auth_cookie(user.id))
        response = client.post("/profile", data={
            "first_name": "Jean", "last_name": "Dupont",
            "email": "user@example.com",
            "phone_number": "0699999999",
        })
        assert response.status_code == 200
        db.expire_all()
        assert user.phone_number == "0699999999"


# ── POST /profile/delete ──────────────────────────────────────────────────────

class TestAccountDelete:

    def test_delete_without_auth_redirects_to_login(self, client):
        response = client.post("/profile/delete", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_delete_deactivates_account(self, client, db):
        user = make_user(db, email="todelete@example.com")
        client.cookies.set("access_token", auth_cookie(user.id))
        client.post("/profile/delete")
        db.expire_all()
        assert user.is_active is False

    def test_delete_clears_access_token_cookie(self, client, db):
        user = make_user(db, email="todelete@example.com")
        client.cookies.set("access_token", auth_cookie(user.id))
        response = client.post("/profile/delete", follow_redirects=False)
        assert response.cookies.get("access_token") == "" or "access_token" not in response.cookies

    def test_delete_redirects_to_home(self, client, db):
        user = make_user(db, email="todelete@example.com")
        client.cookies.set("access_token", auth_cookie(user.id))
        response = client.post("/profile/delete", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/")

    def test_deleted_user_cannot_login(self, client, db):
        user = make_user(db, email="todelete@example.com", password="monpass123")
        client.cookies.set("access_token", auth_cookie(user.id))
        client.post("/profile/delete")
        response = client.post("/login", data={
            "email": "todelete@example.com", "password": "monpass123",
        })
        assert response.status_code == 401
