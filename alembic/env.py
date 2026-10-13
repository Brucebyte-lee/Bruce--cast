"""Alembic environment: tells Alembic which database to use and which models exist."""

from logging.config import fileConfig

from sqlalchemy import create_engine

import app.models  # noqa: F401  (importing registers the tables on Base.metadata)
from alembic import context
from app.core.config import get_settings
from app.database.session import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
DATABASE_URL = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        # render_as_batch lets SQLite apply ALTER-style changes in future migrations
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
