from app.models.user import User
from app.utils.security import create_access_token, hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(db, *, email, password="password123", first_name="Jean", last_name="Dupont",
              is_admin=False, is_active=True):
    user = User(
        first_name=first_name, last_name=last_name, email=email,
        password_hash=hash_password(password), is_admin=is_admin, is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_cookie(user_id, is_admin: bool = False) -> str:
    return create_access_token({"sub": str(int(user_id)), "is_admin": is_admin})


# ── POST /register ────────────────────────────────────────────────────────────

class TestRegister:

    def test_register_redirects_to_login_on_success(self, client):
        response = client.post("/register", data={
            "first_name": "Alice", "last_name": "Martin",
            "email": "alice@example.com", "password": "securepass",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]
        assert "success" in response.headers["location"]

    def test_register_creates_user_in_db(self, client, db):
        client.post("/register", data={
            "first_name": "Alice", "last_name": "Martin",
            "email": "alice@example.com", "password": "securepass",
        })
        user = db.query(User).filter(User.email == "alice@example.com").first()
        assert user is not None
        assert user.first_name == "Alice"
        assert user.is_admin is False

    def test_register_hashes_password(self, client, db):
        client.post("/register", data={
            "first_name": "Bob", "last_name": "Durand",
            "email": "bob@example.com", "password": "mypassword",
        })
        user = db.query(User).filter(User.email == "bob@example.com").first()
        assert user.password_hash != "mypassword"

    def test_register_saves_optional_fields(self, client, db):
        client.post("/register", data={
            "first_name": "Carol", "last_name": "Petit",
            "email": "carol@example.com", "password": "securepass",
            "phone_number": "0600000001", "address": "1 rue de la Paix",
        })
        user = db.query(User).filter(User.email == "carol@example.com").first()
        assert user.phone_number == "0600000001"
        assert user.address == "1 rue de la Paix"

    def test_register_duplicate_email_returns_422(self, client, db):
        make_user(db, email="dup@example.com")
        response = client.post("/register", data={
            "first_name": "Eve", "last_name": "Test",
            "email": "dup@example.com", "password": "securepass",
        })
        assert response.status_code == 422

    def test_register_duplicate_email_shows_error(self, client, db):
        make_user(db, email="dup2@example.com")
        response = client.post("/register", data={
            "first_name": "Eve", "last_name": "Test",
            "email": "dup2@example.com", "password": "securepass",
        })
        assert "existe déjà" in response.text

    def test_register_short_password_returns_422(self, client):
        response = client.post("/register", data={
            "first_name": "Frank", "last_name": "Test",
            "email": "frank@example.com", "password": "abc",
        })
        assert response.status_code == 422

    def test_register_short_password_shows_error(self, client):
        response = client.post("/register", data={
            "first_name": "Frank", "last_name": "Test",
            "email": "frank@example.com", "password": "abc",
        })
        assert "8 caractères" in response.text

    def test_register_empty_first_name_returns_422(self, client):
        response = client.post("/register", data={
            "first_name": "  ", "last_name": "Test",
            "email": "test@example.com", "password": "securepass",
        })
        assert response.status_code == 422

    def test_register_invalid_email_returns_422(self, client):
        response = client.post("/register", data={
            "first_name": "Test", "last_name": "Test",
            "email": "not-an-email", "password": "securepass",
        })
        assert response.status_code == 422


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
