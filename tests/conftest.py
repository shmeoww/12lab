# tests/conftest.py

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import create_application
from app.models.user import User


# ============================================================================
# Event Loop
# ============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Создаёт event loop для всей тестовой сессии.
    """

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Async Engine
# ============================================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Создаёт асинхронный тестовый движок SQLite in-memory.
    """

    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    yield test_engine

    await test_engine.dispose()


# ============================================================================
# Create / Drop Tables
# ============================================================================

@pytest_asyncio.fixture(scope="session")
async def tables(engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """
    Создаёт все таблицы перед тестами
    и удаляет после завершения тестов.
    """

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ============================================================================
# Database Session
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def db_session(
    engine: AsyncEngine,
    tables: None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Создаёт новую AsyncSession для каждого теста.
    После теста выполняется rollback транзакции.
    """

    connection = await engine.connect()
    transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await transaction.rollback()
    await connection.close()


# ============================================================================
# FastAPI Test Client
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Создаёт HTTP клиент с override dependency get_db.
    """

    app = create_application()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()


# ============================================================================
# Test Users
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def admin_user(
    db_session: AsyncSession,
) -> User:
    """
    Создаёт администратора для тестов.
    """

    user = User(
        email="admin@test.com",
        hashed_password=hash_password("Admin123"),
        is_admin=True,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture(scope="function")
async def student_user(
    db_session: AsyncSession,
) -> User:
    """
    Создаёт обычного студента для тестов.
    """

    user = User(
        email="student@test.com",
        hashed_password=hash_password("Student123"),
        is_admin=False,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


# ============================================================================
# JWT Tokens
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def admin_token(admin_user: User) -> str:
    """
    JWT токен администратора.
    """
    return create_access_token(admin_user.email)


@pytest_asyncio.fixture(scope="function")
async def student_token(student_user: User) -> str:
    """
    JWT токен студента.
    """
    return create_access_token(student_user.email)