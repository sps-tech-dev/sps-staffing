"""SQLAlchemy declarative Base — the metadata target for Alembic autogenerate.

Intentionally separate from app boot: this module is imported by Alembic's
env.py, NOT by app.main, so importing SQLAlchemy's ORM here never affects the
dependency-free startup path. No models are defined yet (Phase B creates only
the four schemas); future models subclass Base so autogenerate sees them.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Convenience alias for env.py: target_metadata = metadata
metadata = Base.metadata
