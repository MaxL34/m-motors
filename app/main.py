import sentry_sdk
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import settings
from app.core.logging_config import setup_logging
from app.database import Base, engine
import app.models
from app.middleware.request_logger import RequestLoggerMiddleware
from app.routers import vehicles, admin, pages, auth, profile, client_files, favorites

# ── Logging ───────────────────────────────────────────────────────────────────

setup_logging()

# ── Sentry ────────────────────────────────────────────────────────────────────

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.2,   # 20 % des transactions tracées (performance)
        send_default_pii=False,   # pas de données personnelles envoyées
    )
    logger.info("Sentry initialisé")
else:
    logger.warning("SENTRY_DSN non configuré — alerting désactivé")

# ── App ───────────────────────────────────────────────────────────────────────

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="M-Motors API",
    version="0.1.0",
)

@app.get("/sentry-test")
async def sentry_test():
    raise Exception("Test Sentry - M-Motors")

app.add_middleware(RequestLoggerMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(client_files.router)
app.include_router(favorites.router)
app.include_router(vehicles.router)
app.include_router(admin.router)

logger.info("M-Motors démarré")
