"""Engine, session factory, and FastAPI dependency for the application database."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def create_app_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        # WAL lets reads continue while a write is in progress (FastAPI serves requests concurrently).
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine = create_app_engine(settings.resolved_database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Yield a database session for one request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables that don't exist yet (application DB and knowledge DB)."""
    from app.db import models  # noqa: F401  (registers models on Base.metadata)
    from app.knowledge.db import init_knowledge_db

    Base.metadata.create_all(bind=engine)
    add_missing_nullable_columns(engine, Base)
    init_knowledge_db()


def add_missing_nullable_columns(target: Engine, base: type[DeclarativeBase]) -> None:
    """Minimal migration: add nullable columns that were added to models after a table was created."""
    inspector = inspect(target)
    with target.begin() as connection:
        for table in base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing and column.nullable:
                    column_type = column.type.compile(dialect=target.dialect)
                    connection.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))
