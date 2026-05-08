from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# autocommit=False transactions must be explicitly committed or rolled back
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    """Base class from which all SQLAlchemy models should inherit."""
    pass

def get_db():
    """Dependency that provides a database session.
    This function is designed to be used with FastAPI's dependency injection system.
    It creates a new database session for each request and ensures that the session is properly closed after the request is completed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()