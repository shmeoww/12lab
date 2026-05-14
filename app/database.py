"""
app/database.py

Настройка асинхронного подключения к SQLite через SQLAlchemy 2.x.

Схема работы:
  AsyncEngine → AsyncSessionFactory → AsyncSession (на каждый запрос)

Использование в роутерах:
    from app.database import get_db
    ...
    async def endpoint(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User))
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ── Движок ───────────────────────────────────────────────────────────────────
# echo=True выводит SQL-запросы в консоль (удобно при DEBUG)
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

# ── Фабрика сессий ───────────────────────────────────────────────────────────
# expire_on_commit=False — объекты остаются доступны после commit()
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Базовый класс для всех ORM-моделей ───────────────────────────────────────
class Base(DeclarativeBase):
    """
    Единый декларативный базовый класс.
    Все модели наследуются от него:
        class User(Base):
            __tablename__ = "users"
    """
    pass


# ── Dependency для FastAPI ────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency, предоставляющий сессию БД на время запроса.

    При любой ошибке транзакция откатывается, сессия закрывается.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Вспомогательные функции ───────────────────────────────────────────────────
async def create_all_tables() -> None:
    """
    Создаёт все таблицы по метаданным ORM-моделей.
    Вызывается при старте приложения (только в dev/тестах).
    В продакшне используй Alembic-миграции.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """Удаляет все таблицы. Используется в тестах (setup/teardown)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

from typing import Annotated
from fastapi import Depends

# Готовый тип для использования в роутерах:
# async def endpoint(db: DbSession): ...
DbSession = Annotated[AsyncSession, Depends(get_db)]
