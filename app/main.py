from fastapi import FastAPI

from app.config import settings
from app.database import Base, engine
import app.models  # noqa: F401 — ensure all models are registered before create_all

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="M-Motors API",
    version="0.1.0",
)