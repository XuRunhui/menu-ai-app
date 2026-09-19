"""Engine and session factory for the knowledge database."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.db.session import create_app_engine


class KnowledgeBase(DeclarativeBase):
    """Declarative base for knowledge models (separate metadata from the app database)."""


knowledge_engine = create_app_engine(settings.resolved_knowledge_database_url)
KnowledgeSession = sessionmaker(bind=knowledge_engine, autoflush=False, expire_on_commit=False)


@contextmanager
def knowledge_session() -> Iterator[Session]:
    db = KnowledgeSession()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_knowledge_db() -> None:
    from app.knowledge import models  # noqa: F401  (registers models)

    KnowledgeBase.metadata.create_all(bind=knowledge_engine)
