from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
import app.models
from app.routers import vehicles, admin, pages, auth, profile, client_files, favorites

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="M-Motors API",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(client_files.router)
app.include_router(favorites.router)
app.include_router(vehicles.router)
app.include_router(admin.router)