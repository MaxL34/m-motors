from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.otp_code import OtpCode
from app.models.user import User
from app.services.otp_service import create_registration_otp, verify_registration_otp
from app.utils.security import create_access_token, hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(db, *, email, password="password123", first_name="Jean", last_name="Dupont",
              phone_number=None, is_admin=False, is_active=True):
    user = User(
        first_name=first_name, last_name=last_name, email=email,
        phone_number=phone_number,
        password_hash=hash_password(password), is_admin=is_admin, is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_cookie(user_id, is_admin: bool = False) -> str:
    return create_access_token({"sub": str(int(user_id)), "is_admin": is_admin})


def post_register(client, *, phone_number="0600000001", **overrides):
    """POST /register en mockant l'envoi SMS. Retourne la response."""
    data = {
        "first_name": "Alice", "last_name": "Martin",
        "email": "alice@example.com", "password": "securepass",
        "phone_number": phone_number,
        **overrides,
    }
    with patch("app.routers.auth.send_otp_sms"):
        return client.post("/register", data=data, follow_redirects=False)


def register_and_get_otp(client, db, *, phone_number="0600000001", **overrides):
    """Inscrit un utilisateur et retourne (pending_token, code) pour la vérification."""
    response = post_register(client, phone_number=phone_number, **overrides)
    pending_token = response.cookies.get("pending_otp_token")
    otp = db.query(OtpCode).filter(OtpCode.pending_token == pending_token).first()
    return pending_token, otp.code


# ── POST /register ────────────────────────────────────────────────────────────

class TestRegister:

    def test_register_with_phone_redirects_to_verify(self, client):
        response = post_register(client)
        assert response.status_code == 303
        assert "/register/verify" in response.headers["location"]

    def test_register_with_phone_sets_pending_cookie(self, client):
        response = post_register(client)
        assert "pending_otp_token" in response.cookies

    def test_register_does_not_create_user_before_otp(self, client, db):
        post_register(client)
        user = db.query(User).filter(User.email == "alice@example.com").first()
        assert user is None

    def test_register_creates_otp_in_db(self, client, db):
        post_register(client)
        otp = db.query(OtpCode).first()
        assert otp is not None
        assert otp.registration_json is not None

    def test_register_otp_stores_hashed_password(self, client, db):
        post_register(client)
        import json
        otp = db.query(OtpCode).first()
        data = json.loads(otp.registration_json)
        assert "password_hash" in data
        assert data["password_hash"] != "securepass"

    def test_register_calls_send_otp_sms(self, client):
        with patch("app.routers.auth.send_otp_sms") as mock_sms:
            client.post("/register", data={
                "first_name": "Alice", "last_name": "Martin",
                "email": "alice@example.com", "password": "securepass",
                "phone_number": "0600000001",
            }, follow_redirects=False)
            mock_sms.assert_called_once_with("0600000001", pytest.approx(mock_sms.call_args[0][1]))

    def test_register_without_phone_returns_422(self, client):
        with patch("app.routers.auth.send_otp_sms"):
            response = client.post("/register", data={
                "first_name": "Alice", "last_name": "Martin",
                "email": "alice@example.com", "password": "securepass",
            }, follow_redirects=False)
        assert response.status_code == 422

    def test_register_duplicate_email_returns_422(self, client, db):
        make_user(db, email="alice@example.com", phone_number="0600000001")
        response = post_register(client)
        assert response.status_code == 422

    def test_register_duplicate_email_shows_error(self, client, db):
        make_user(db, email="alice@example.com", phone_number="0600000002")
        response = post_register(client)
        assert "existe déjà" in response.text

    def test_register_short_password_returns_422(self, client):
        response = post_register(client, password="abc")
        assert response.status_code == 422

    def test_register_short_password_shows_error(self, client):
        response = post_register(client, password="abc")
        assert "8 caractères" in response.text

    def test_register_empty_first_name_returns_422(self, client):
        response = post_register(client, first_name="  ")
        assert response.status_code == 422

    def test_register_invalid_email_returns_422(self, client):
        response = post_register(client, email="not-an-email")
        assert response.status_code == 422


# ── GET /register/verify ──────────────────────────────────────────────────────

class TestGetRegisterVerify:

    def test_without_cookie_redirects_to_register(self, client):
        response = client.get("/register/verify", follow_redirects=False)
        assert response.status_code == 303
        assert "/register" in response.headers["location"]

    def test_with_cookie_returns_200(self, client, db):
        response = post_register(client)
        pending_token = response.cookies.get("pending_otp_token")
        client.cookies.set("pending_otp_token", pending_token)
        response = client.get("/register/verify", follow_redirects=False)
        assert response.status_code == 200

    def test_with_cookie_shows_otp_form(self, client, db):
        response = post_register(client)
        pending_token = response.cookies.get("pending_otp_token")
        client.cookies.set("pending_otp_token", pending_token)
        response = client.get("/register/verify")
        assert "register/verify" in response.text


# ── POST /register/verify ─────────────────────────────────────────────────────

class TestPostRegisterVerify:

    def test_valid_code_creates_user(self, client, db):
        pending_token, code = register_and_get_otp(client, db)
        client.cookies.set("pending_otp_token", pending_token)
        client.post("/register/verify", data={"code": code})
        user = db.query(User).filter(User.email == "alice@example.com").first()
        assert user is not None

    def test_valid_code_redirects_to_login(self, client, db):
        pending_token, code = register_and_get_otp(client, db)
        client.cookies.set("pending_otp_token", pending_token)
        response = client.post("/register/verify", data={"code": code}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_valid_code_includes_success_message(self, client, db):
        pending_token, code = register_and_get_otp(client, db)
        client.cookies.set("pending_otp_token", pending_token)
        response = client.post("/register/verify", data={"code": code}, follow_redirects=False)
        assert "success" in response.headers["location"]

    def test_valid_code_clears_pending_cookie(self, client, db):
        pending_token, code = register_and_get_otp(client, db)
        client.cookies.set("pending_otp_token", pending_token)
        response = client.post("/register/verify", data={"code": code}, follow_redirects=False)
        assert response.cookies.get("pending_otp_token") == "" or "pending_otp_token" not in response.cookies

    def test_valid_code_marks_otp_as_used(self, client, db):
        pending_token, code = register_and_get_otp(client, db)
        client.cookies.set("pending_otp_token", pending_token)
        client.post("/register/verify", data={"code": code})
        db.expire_all()
        otp = db.query(OtpCode).filter(OtpCode.pending_token == pending_token).first()
        assert otp.used is True

    def test_wrong_code_returns_422(self, client, db):
        pending_token, _ = register_and_get_otp(client, db)
        client.cookies.set("pending_otp_token", pending_token)
        response = client.post("/register/verify", data={"code": "000000"})
        assert response.status_code == 422

    def test_wrong_code_shows_remaining_attempts(self, client, db):
        pending_token, _ = register_and_get_otp(client, db)
        client.cookies.set("pending_otp_token", pending_token)
        response = client.post("/register/verify", data={"code": "000000"})
        assert "tentative" in response.text

    def test_wrong_code_does_not_create_user(self, client, db):
        pending_token, _ = register_and_get_otp(client, db)
        client.cookies.set("pending_otp_token", pending_token)
        client.post("/register/verify", data={"code": "000000"})
        user = db.query(User).filter(User.email == "alice@example.com").first()
        assert user is None

    def test_max_attempts_redirects_to_register(self, client, db):
        pending_token, _ = register_and_get_otp(client, db)
        client.cookies.set("pending_otp_token", pending_token)
        for _ in range(3):
            response = client.post("/register/verify", data={"code": "000000"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/register" in response.headers["location"]

    def test_without_cookie_redirects_to_register(self, client):
        response = client.post("/register/verify", data={"code": "123456"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/register" in response.headers["location"]


# ── Tests unitaires — otp_service ─────────────────────────────────────────────

class TestOtpService:

    def _make_otp(self, db, registration_data=None):
        data = registration_data or {
            "first_name": "Alice", "last_name": "Martin",
            "email": "alice@example.com", "phone_number": "0600000001",
            "address": None, "password_hash": hash_password("securepass"),
        }
        return create_registration_otp(db, data)

    def test_create_otp_stores_registration_json(self, db):
        otp = self._make_otp(db)
        assert otp.registration_json is not None
        import json
        data = json.loads(otp.registration_json)
        assert data["email"] == "alice@example.com"

    def test_create_otp_generates_6_digit_code(self, db):
        otp = self._make_otp(db)
        assert len(otp.code) == 6
        assert otp.code.isdigit()

    def test_create_otp_sets_expiry(self, db):
        otp = self._make_otp(db)
        assert otp.expires_at > datetime.utcnow()

    def test_create_otp_starts_unused(self, db):
        otp = self._make_otp(db)
        assert otp.used is False
        assert otp.attempts == 0

    def test_verify_valid_code_returns_success(self, db):
        otp = self._make_otp(db)
        success, _, data = verify_registration_otp(db, otp.pending_token, otp.code)
        assert success is True
        assert data["email"] == "alice@example.com"

    def test_verify_valid_code_marks_otp_used(self, db):
        otp = self._make_otp(db)
        verify_registration_otp(db, otp.pending_token, otp.code)
        db.expire_all()
        assert otp.used is True

    def test_verify_wrong_code_returns_failure(self, db):
        otp = self._make_otp(db)
        success, error, data = verify_registration_otp(db, otp.pending_token, "000000")
        assert success is False
        assert data is None
        assert "incorrect" in error.lower() or "tentative" in error.lower()

    def test_verify_wrong_code_increments_attempts(self, db):
        otp = self._make_otp(db)
        verify_registration_otp(db, otp.pending_token, "000000")
        db.expire_all()
        assert otp.attempts == 1

    def test_verify_invalid_token_returns_failure(self, db):
        success, error, data = verify_registration_otp(db, "token-inexistant", "123456")
        assert success is False
        assert "invalide" in error.lower()
        assert data is None

    def test_verify_used_otp_returns_failure(self, db):
        otp = self._make_otp(db)
        verify_registration_otp(db, otp.pending_token, otp.code)
        success, error, data = verify_registration_otp(db, otp.pending_token, otp.code)
        assert success is False
        assert data is None

    def test_verify_expired_otp_returns_failure(self, db):
        otp = self._make_otp(db)
        otp.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        success, error, data = verify_registration_otp(db, otp.pending_token, otp.code)
        assert success is False
        assert "expiré" in error.lower()
        assert data is None

    def test_verify_max_attempts_blocks_correct_code(self, db):
        otp = self._make_otp(db)
        otp.attempts = 3
        db.commit()
        success, error, data = verify_registration_otp(db, otp.pending_token, otp.code)
        assert success is False
        assert data is None


# ── POST /login ───────────────────────────────────────────────────────────────

class TestLogin:

    def test_login_sets_cookie_on_success(self, client, db):
        make_user(db, email="user@example.com", password="goodpass")
        response = client.post("/login", data={
            "email": "user@example.com", "password": "goodpass",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert "access_token" in response.cookies

    def test_login_redirects_to_homepage(self, client, db):
        make_user(db, email="user2@example.com", password="goodpass")
        response = client.post("/login", data={
            "email": "user2@example.com", "password": "goodpass",
        }, follow_redirects=False)
        assert response.headers["location"] == "/"

    def test_login_wrong_password_returns_401(self, client, db):
        make_user(db, email="user3@example.com", password="correctpass")
        response = client.post("/login", data={
            "email": "user3@example.com", "password": "wrongpass",
        })
        assert response.status_code == 401

    def test_login_wrong_password_shows_error(self, client, db):
        make_user(db, email="user4@example.com", password="correctpass")
        response = client.post("/login", data={
            "email": "user4@example.com", "password": "wrongpass",
        })
        assert "incorrect" in response.text

    def test_login_unknown_email_returns_401(self, client):
        response = client.post("/login", data={
            "email": "ghost@example.com", "password": "anything",
        })
        assert response.status_code == 401

    def test_login_inactive_user_returns_401(self, client, db):
        make_user(db, email="inactive@example.com", password="goodpass", is_active=False)
        response = client.post("/login", data={
            "email": "inactive@example.com", "password": "goodpass",
        })
        assert response.status_code == 401

    def test_login_admin_via_user_route_returns_403(self, client, db):
        make_user(db, email="admin@example.com", password="adminpass", is_admin=True)
        response = client.post("/login", data={
            "email": "admin@example.com", "password": "adminpass",
        })
        assert response.status_code == 403

    def test_login_admin_via_user_route_shows_error(self, client, db):
        make_user(db, email="admin2@example.com", password="adminpass", is_admin=True)
        response = client.post("/login", data={
            "email": "admin2@example.com", "password": "adminpass",
        })
        assert "espace admin" in response.text

    def test_login_does_not_require_otp(self, client, db):
        make_user(db, email="user5@example.com", password="goodpass", phone_number="0600000001")
        response = client.post("/login", data={
            "email": "user5@example.com", "password": "goodpass",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert "access_token" in response.cookies

    def test_login_increments_failed_attempts_on_wrong_password(self, client, db):
        user = make_user(db, email="user6@example.com", password="correctpass")
        client.post("/login", data={"email": "user6@example.com", "password": "wrong"})
        db.expire_all()
        assert user.failed_login_attempts == 1

    def test_login_resets_attempts_on_success(self, client, db):
        user = make_user(db, email="user7@example.com", password="correctpass")
        user.failed_login_attempts = 2
        db.commit()
        client.post("/login", data={"email": "user7@example.com", "password": "correctpass"})
        db.expire_all()
        assert user.failed_login_attempts == 0

    def test_login_locks_account_after_max_attempts(self, client, db):
        user = make_user(db, email="user8@example.com", password="correctpass")
        for _ in range(3):
            client.post("/login", data={"email": "user8@example.com", "password": "wrong"})
        db.expire_all()
        assert user.is_locked is True

    def test_login_locked_account_returns_403(self, client, db):
        user = make_user(db, email="user9@example.com", password="correctpass")
        user.is_locked = True
        db.commit()
        response = client.post("/login", data={"email": "user9@example.com", "password": "correctpass"})
        assert response.status_code == 403

    def test_login_locked_account_shows_message(self, client, db):
        user = make_user(db, email="user10@example.com", password="correctpass")
        user.is_locked = True
        db.commit()
        response = client.post("/login", data={"email": "user10@example.com", "password": "correctpass"})
        assert "bloqué" in response.text

    def test_login_locked_account_cannot_login_with_correct_password(self, client, db):
        user = make_user(db, email="user11@example.com", password="correctpass")
        user.is_locked = True
        db.commit()
        response = client.post("/login", data={"email": "user11@example.com", "password": "correctpass"}, follow_redirects=False)
        assert "access_token" not in response.cookies


# ── POST /admin/login ─────────────────────────────────────────────────────────

class TestAdminLogin:

    def test_admin_login_sets_cookie_on_success(self, client, db):
        make_user(db, email="admin@example.com", password="adminpass", is_admin=True)
        response = client.post("/admin/login", data={
            "email": "admin@example.com", "password": "adminpass",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert "access_token" in response.cookies

    def test_admin_login_redirects_to_admin_vehicles(self, client, db):
        make_user(db, email="admin2@example.com", password="adminpass", is_admin=True)
        response = client.post("/admin/login", data={
            "email": "admin2@example.com", "password": "adminpass",
        }, follow_redirects=False)
        assert response.headers["location"] == "/admin/vehicles"

    def test_admin_login_wrong_password_returns_401(self, client, db):
        make_user(db, email="admin3@example.com", password="correct", is_admin=True)
        response = client.post("/admin/login", data={
            "email": "admin3@example.com", "password": "wrong",
        })
        assert response.status_code == 401

    def test_admin_login_regular_user_returns_401(self, client, db):
        make_user(db, email="user@example.com", password="userpass", is_admin=False)
        response = client.post("/admin/login", data={
            "email": "user@example.com", "password": "userpass",
        })
        assert response.status_code == 401

    def test_admin_login_shows_error_on_failure(self, client, db):
        response = client.post("/admin/login", data={
            "email": "nobody@example.com", "password": "wrong",
        })
        assert "Identifiants invalides" in response.text


# ── GET /logout ───────────────────────────────────────────────────────────────

class TestLogout:

    def test_logout_clears_cookie(self, client, db):
        user = make_user(db, email="logout@example.com", password="pass1234")
        client.cookies.set("access_token", auth_cookie(user.id))
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.cookies.get("access_token") == "" or "access_token" not in response.cookies

    def test_logout_redirects_to_homepage(self, client, db):
        user = make_user(db, email="logout2@example.com", password="pass1234")
        client.cookies.set("access_token", auth_cookie(user.id))
        response = client.get("/logout", follow_redirects=False)
        assert response.headers["location"] == "/"


# ── Protection routes admin ───────────────────────────────────────────────────

class TestAdminProtection:

    def test_admin_vehicles_without_cookie_redirects(self, client):
        response = client.get("/admin/vehicles", follow_redirects=False)
        assert response.status_code == 303
        assert "/admin/login" in response.headers["location"]

    def test_admin_vehicles_with_user_cookie_redirects(self, client, db):
        user = make_user(db, email="nonadmin@example.com", password="pass1234", is_admin=False)
        client.cookies.set("access_token", auth_cookie(user.id, is_admin=False))
        response = client.get("/admin/vehicles", follow_redirects=False)
        assert response.status_code == 303
        assert "/admin/login" in response.headers["location"]

    def test_admin_vehicles_with_admin_cookie_returns_200(self, client, db):
        admin = make_user(db, email="realadmin@example.com", password="pass1234", is_admin=True)
        client.cookies.set("access_token", auth_cookie(admin.id, is_admin=True))
        response = client.get("/admin/vehicles")
        assert response.status_code == 200

    def test_admin_vehicle_detail_requires_auth(self, client):
        response = client.get("/admin/vehicles/1", follow_redirects=False)
        assert response.status_code == 303

    def test_admin_create_requires_auth(self, client):
        response = client.get("/admin/vehicles/new", follow_redirects=False)
        assert response.status_code == 303

    def test_admin_invalid_token_redirects(self, client):
        client.cookies.set("access_token", "token.invalide.xxx")
        response = client.get("/admin/vehicles", follow_redirects=False)
        assert response.status_code == 303
        assert "/admin/login" in response.headers["location"]
