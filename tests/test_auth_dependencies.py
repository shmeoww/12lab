# tests/test_auth_dependencies.py

from datetime import datetime, timezone
import uuid

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token
from app.config import get_settings
from app.models.user import User


# ============================================================================
# Helpers
# ============================================================================

def make_expired_token(email: str) -> str:
    """
    Создаёт просроченный access JWT токен.
    """

    settings = get_settings()

    payload = {
        "sub": email,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": datetime(2020, 1, 1, tzinfo=timezone.utc),
        "exp": datetime(2020, 1, 2, tzinfo=timezone.utc),
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


# ============================================================================
# Tests for app/auth/dependencies.py
# ============================================================================

@pytest.mark.asyncio
async def test_expired_token_returns_401(
    client: AsyncClient,
) -> None:
    """
    Просроченный JWT токен должен вернуть 401.
    """

    expired_token = make_expired_token(
        "expired@test.com"
    )

    response = await client.get(
        "/api/v1/enrollments/my",
        headers={
            "Authorization": f"Bearer {expired_token}"
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deleted_user_token_returns_401(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """
    Если пользователь удалён после выдачи токена —
    запросы с этим токеном должны вернуть 401.
    """

    # Создаём пользователя
    user = User(
        email="deleted@test.com",
        hashed_password="hashed",
        is_active=True,
        is_admin=False,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Выдаём токен
    access_token = create_access_token(user.email)

    # Удаляем пользователя
    await db_session.delete(user)
    await db_session.commit()

    # Выполняем запрос
    response = await client.get(
        "/api/v1/enrollments/my",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_protected_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user,
    student_token: str,
) -> None:
    """
    Неактивный пользователь не должен иметь доступ
    к защищённым эндпоинтам.
    """

    # Деактивируем пользователя
    student_user.is_active = False

    db_session.add(student_user)
    await db_session.commit()
    await db_session.refresh(student_user)

    response = await client.get(
        "/api/v1/enrollments/my",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code in (401, 403)


# ============================================================================
# Tests for app/routers/auth.py
# ============================================================================

@pytest.mark.asyncio
async def test_register_existing_email_detail(
    client: AsyncClient,
) -> None:
    """
    При регистрации существующего email
    detail должен содержать email пользователя.
    """

    payload = {
        "email": "duplicate@test.com",
        "password": "StrongPass123",
        "full_name": "Duplicate User",
    }

    # Первая регистрация
    first_response = await client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    assert first_response.status_code == 201

    # Повторная регистрация
    second_response = await client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    data = second_response.json()

    assert second_response.status_code == 409

    # Проверяем detail
    assert "detail" in data
    assert "email" in data["detail"].lower()


@pytest.mark.asyncio
async def test_login_and_check_token_structure(
    client: AsyncClient,
    student_user,
) -> None:
    """
    Проверка структуры access_token после логина.
    """

    settings = get_settings()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": student_user.email,
            "password": "Student123",
        },
    )

    data = response.json()

    assert response.status_code == 200

    access_token = data["access_token"]

    # Декодируем JWT
    payload = jwt.decode(
        access_token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )

    # Проверяем payload
    assert payload["sub"] == student_user.email
    assert payload["type"] == "access"

    # JWT ID должен присутствовать
    assert "jti" in payload
    assert payload["jti"]


@pytest.mark.asyncio
async def test_refresh_preserves_user(
    client: AsyncClient,
    student_user,
) -> None:
    """
    После refresh новый access token
    должен принадлежать тому же пользователю.
    """

    # Логин
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": student_user.email,
            "password": "Student123",
        },
    )

    login_data = login_response.json()

    refresh_token = login_data["refresh_token"]

    # Refresh токенов
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    refresh_data = refresh_response.json()

    assert refresh_response.status_code == 200

    new_access_token = refresh_data["access_token"]

    # Проверяем доступ к API новым токеном
    protected_response = await client.get(
        "/api/v1/enrollments/my",
        headers={
            "Authorization": f"Bearer {new_access_token}"
        },
    )

    assert protected_response.status_code == 200