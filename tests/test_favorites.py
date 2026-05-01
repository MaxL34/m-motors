from app.models.favorite import Favorite
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleStatus, FuelType, TransmissionType
from app.services.favorite_service import get_favorites, is_favorite, toggle_favorite
from app.utils.security import create_access_token, hash_password


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(db, *, email="user@example.com", password="password123", is_admin=False):
    user = User(
        first_name="Jean", last_name="Dupont", email=email,
        password_hash=hash_password(password), is_admin=is_admin, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_vehicle(db, *, vin="VIN001", licence_plate="AA-000-AA"):
    v = Vehicle(
        vin=vin, licence_plate=licence_plate,
        brand="Renault", model="Clio", year=2022,
        fuel_type=FuelType.PETROL, transmission_type=TransmissionType.MANUAL,
        mileage=10000, is_for_sale=True, selling_price=12000.0,
        status=VehicleStatus.ACTIVE,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def user_cookie(user_id: int, is_admin: bool = False) -> str:
    return create_access_token({"sub": str(user_id), "is_admin": is_admin})


# ── favorite_service : get_favorites ─────────────────────────────────────────

class TestGetFavorites:

    def test_returns_empty_list_when_no_favorites(self, db):
        user = make_user(db)
        assert get_favorites(db, user.id) == []

    def test_returns_favorited_vehicle(self, db):
        user = make_user(db)
        v = make_vehicle(db)
        db.add(Favorite(user_id=user.id, vehicle_id=v.id))
        db.commit()
        result = get_favorites(db, user.id)
        assert len(result) == 1
        assert result[0].id == v.id

    def test_does_not_return_other_users_favorites(self, db):
        user1 = make_user(db, email="u1@example.com")
        user2 = make_user(db, email="u2@example.com")
        v = make_vehicle(db)
        db.add(Favorite(user_id=user2.id, vehicle_id=v.id))
        db.commit()
        assert get_favorites(db, user1.id) == []

    def test_returns_multiple_favorites(self, db):
        user = make_user(db)
        v1 = make_vehicle(db, vin="V1", licence_plate="AA-001-AA")
        v2 = make_vehicle(db, vin="V2", licence_plate="AA-002-AA")
        db.add(Favorite(user_id=user.id, vehicle_id=v1.id))
        db.add(Favorite(user_id=user.id, vehicle_id=v2.id))
        db.commit()
        assert len(get_favorites(db, user.id)) == 2


# ── favorite_service : is_favorite ───────────────────────────────────────────

class TestIsFavorite:

    def test_returns_false_when_not_favorited(self, db):
        user = make_user(db)
        v = make_vehicle(db)
        assert is_favorite(db, user.id, v.id) is False

    def test_returns_true_when_favorited(self, db):
        user = make_user(db)
        v = make_vehicle(db)
        db.add(Favorite(user_id=user.id, vehicle_id=v.id))
        db.commit()
        assert is_favorite(db, user.id, v.id) is True

    def test_does_not_leak_between_users(self, db):
        user1 = make_user(db, email="u1@example.com")
        user2 = make_user(db, email="u2@example.com")
        v = make_vehicle(db)
        db.add(Favorite(user_id=user2.id, vehicle_id=v.id))
        db.commit()
        assert is_favorite(db, user1.id, v.id) is False


# ── favorite_service : toggle_favorite ───────────────────────────────────────

class TestToggleFavorite:

    def test_adds_favorite_when_not_present(self, db):
        user = make_user(db)
        v = make_vehicle(db)
        result = toggle_favorite(db, user.id, v.id)
        assert result is True
        assert db.query(Favorite).filter_by(user_id=user.id, vehicle_id=v.id).first() is not None

    def test_removes_favorite_when_already_present(self, db):
        user = make_user(db)
        v = make_vehicle(db)
        db.add(Favorite(user_id=user.id, vehicle_id=v.id))
        db.commit()
        result = toggle_favorite(db, user.id, v.id)
        assert result is False
        assert db.query(Favorite).filter_by(user_id=user.id, vehicle_id=v.id).first() is None

    def test_toggle_twice_leaves_no_favorite(self, db):
        user = make_user(db)
        v = make_vehicle(db)
        toggle_favorite(db, user.id, v.id)
        toggle_favorite(db, user.id, v.id)
        assert is_favorite(db, user.id, v.id) is False


# ── POST /vehicles/{id}/favorite ─────────────────────────────────────────────

class TestToggleFavoriteRoute:

    def test_unauthenticated_redirects_to_login(self, client, db):
        v = make_vehicle(db)
        response = client.post(f"/vehicles/{v.id}/favorite", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_adds_favorite_and_redirects(self, client, db):
        user = make_user(db)
        v = make_vehicle(db)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.post(f"/vehicles/{v.id}/favorite", follow_redirects=False)
        assert response.status_code == 303
        assert db.query(Favorite).filter_by(user_id=user.id, vehicle_id=v.id).first() is not None

    def test_removes_favorite_on_second_call(self, client, db):
        user = make_user(db)
        v = make_vehicle(db)
        db.add(Favorite(user_id=user.id, vehicle_id=v.id))
        db.commit()
        client.cookies.set("access_token", user_cookie(user.id))
        client.post(f"/vehicles/{v.id}/favorite", follow_redirects=False)
        assert db.query(Favorite).filter_by(user_id=user.id, vehicle_id=v.id).first() is None

    def test_redirects_to_referer_when_provided(self, client, db):
        user = make_user(db)
        v = make_vehicle(db)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.post(
            f"/vehicles/{v.id}/favorite",
            headers={"referer": f"/vehicles/{v.id}"},
            follow_redirects=False,
        )
        assert f"/vehicles/{v.id}" in response.headers["location"]


# ── GET /favorites ────────────────────────────────────────────────────────────

class TestFavoritesPage:

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/favorites", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_authenticated_returns_200(self, client, db):
        user = make_user(db)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get("/favorites")
        assert response.status_code == 200

    def test_shows_favorited_vehicle(self, client, db):
        user = make_user(db)
        v = make_vehicle(db)
        db.add(Favorite(user_id=user.id, vehicle_id=v.id))
        db.commit()
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get("/favorites")
        assert "Renault" in response.text
        assert "Clio" in response.text

    def test_empty_list_returns_200_without_vehicles(self, client, db):
        user = make_user(db)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get("/favorites")
        assert response.status_code == 200
        assert "Renault" not in response.text


# ── POST /login → redirection vers /vehicles ─────────────────────────────────

class TestLoginRedirect:

    def test_user_login_redirects_to_vehicles(self, client, db):
        make_user(db, email="user@example.com", password="password123")
        response = client.post("/login", data={
            "email": "user@example.com",
            "password": "password123",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/vehicles"

    def test_admin_login_does_not_redirect_to_vehicles(self, client, db):
        make_user(db, email="admin@example.com", password="password123", is_admin=True)
        response = client.post("/login", data={
            "email": "admin@example.com",
            "password": "password123",
        }, follow_redirects=False)
        assert response.headers.get("location") != "/vehicles"


# ── GET /vehicles — sidebar favoris ──────────────────────────────────────────

class TestCatalogFavoritesSidebar:

    def test_sidebar_visible_when_user_has_favorites(self, client, db):
        user = make_user(db)
        v = make_vehicle(db)
        db.add(Favorite(user_id=user.id, vehicle_id=v.id))
        db.commit()
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get("/vehicles")
        assert "Mes favoris" in response.text

    def test_sidebar_hidden_when_no_favorites(self, client, db):
        user = make_user(db)
        client.cookies.set("access_token", user_cookie(user.id))
        response = client.get("/vehicles")
        assert "Mes favoris" not in response.text

    def test_sidebar_hidden_when_not_logged_in(self, client):
        response = client.get("/vehicles")
        assert "Mes favoris" not in response.text
