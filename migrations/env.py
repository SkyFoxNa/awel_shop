import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Імпортуємо ваші налаштування та базу
from config import DATABASE_URL
from db.base import Base
import db.models  # Важливо для реєстрації всіх моделей у метаданих

# Об'єкт конфігурації Alembic
config = context.config

# Налаштування логування
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метадані ваших моделей
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск міграцій в 'offline' режимі (генерує SQL-скрипт)"""
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Безпосереднє виконання міграцій у синхронному контексті всередині асинхронного"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # render_as_batch=True — розкоментуйте, якщо використовуєте SQLite
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Створення асинхронного двигуна та запуск міграцій"""

    # Використовуємо DATABASE_URL з вашого config.py
    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Запуск міграцій в 'online' режимі"""
    # Оскільки ми працюємо з асинхронним драйвером (asyncpg), 
    # запускаємо через подієвий цикл (event loop)
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()