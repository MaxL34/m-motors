from sqlalchemy.orm import Session

from app.models.favorite import Favorite
from app.models.vehicle import Vehicle


def get_favorites(db: Session, user_id: int) -> list[Vehicle]:
    return (
        db.query(Vehicle)
        .join(Favorite, Favorite.vehicle_id == Vehicle.id)
        .filter(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())
        .all()
    )


def is_favorite(db: Session, user_id: int, vehicle_id: int) -> bool:
    return db.query(Favorite).filter_by(user_id=user_id, vehicle_id=vehicle_id).first() is not None


def toggle_favorite(db: Session, user_id: int, vehicle_id: int) -> bool:
    existing = db.query(Favorite).filter_by(user_id=user_id, vehicle_id=vehicle_id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return False
    db.add(Favorite(user_id=user_id, vehicle_id=vehicle_id))
    db.commit()
    return True
