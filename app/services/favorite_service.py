from sqlalchemy.orm import Session

from app.models.favorite import Favorite
from app.models.vehicle import Vehicle


def get_favorites(db: Session, user_id: int) -> list[Vehicle]:
    favorites = db.query(Favorite).filter(Favorite.user_id == user_id).all()
    return [f.vehicle for f in favorites]


def is_favorite(db: Session, user_id: int, vehicle_id: int) -> bool:
    return db.query(Favorite).filter(
        Favorite.user_id == user_id,
        Favorite.vehicle_id == vehicle_id,
    ).first() is not None


def toggle_favorite(db: Session, user_id: int, vehicle_id: int) -> bool:
    """Ajoute ou retire un favori. Retourne True si ajouté, False si retiré."""
    existing = db.query(Favorite).filter(
        Favorite.user_id == user_id,
        Favorite.vehicle_id == vehicle_id,
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        return False
    db.add(Favorite(user_id=user_id, vehicle_id=vehicle_id))
    db.commit()
    return True
