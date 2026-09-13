"""
GridMind — Database Engine & Session
======================================
SQLAlchemy setup with engine, session factory, and Base model.
Supports SQLite (local) and PostgreSQL (future) via DATABASE_URL.

Usage by modules:
    from backend.common.database import get_db_session, Base, engine

    # In FastAPI route:
    @router.get("/data")
    def get_data(db: Session = Depends(get_db_session)):
        return db.query(SomeModel).all()

    # For standalone scripts:
    with get_db_session_context() as db:
        db.query(SomeModel).all()
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.common.config import settings
from backend.common.logger import get_module_logger

log = get_module_logger("database")


# ---------------------------------------------------------------------------
# SQLAlchemy Base — all ORM models inherit from this
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    Every model in common/models/ inherits from this.
    """
    pass


# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------
def _create_engine():
    """
    Create the SQLAlchemy engine based on DATABASE_URL.
    Handles SQLite-specific settings (check_same_thread, WAL mode).
    """
    url = settings.DATABASE_URL
    is_sqlite = url.startswith("sqlite")

    engine_kwargs = {
        "echo": settings.DEBUG and settings.LOG_LEVEL == "DEBUG",
        "pool_pre_ping": True,
    }

    if is_sqlite:
        # SQLite needs check_same_thread=False for FastAPI (multi-threaded)
        engine_kwargs["connect_args"] = {"check_same_thread": False}

        # Ensure the database directory exists
        db_path = url.replace("sqlite:///", "")
        if db_path.startswith("./"):
            db_path = str(settings.PROJECT_ROOT / db_path[2:])
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    else:
        # PostgreSQL pool settings
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20

    _engine = create_engine(url, **engine_kwargs)

    # Enable WAL mode for SQLite (better concurrent read performance)
    if is_sqlite:
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    log.info(f"Database engine created: {'SQLite' if is_sqlite else 'PostgreSQL'}")
    return _engine


engine = _create_engine()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency — yields a database session per request.
    Automatically commits on success, rolls back on error, and closes.

    Usage in a FastAPI route:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db_session)):
            return db.query(Item).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_db_session_context() -> Generator[Session, None, None]:
    """
    Context manager for non-FastAPI usage (scripts, tests, background tasks).

    Usage:
        with get_db_session_context() as db:
            results = db.query(SomeModel).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
