# tests/test_auth.py

import pytest
from httpx import AsyncClient

from app.auth.security import create_access_token


# ============================================================================
# Registration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    """
    Успешная регистрация нового пользователя.
    """

    payload = {
        "email": "newuser@test.com",
        "password": "StrongPass123",
        "full_name": "New User",
    }

    response = await client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    data = response.json()

    assert response.status_code == 201

    # Проверяем основные поля ответа
    assert data["email"] == payload["email"]
    assert data["full_name"] == payload["full_name"]

    # Пароль не должен возвращаться
    assert "password" not in data
    assert "hashed_password" not in data

    # Должен быть id пользователя
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    """
    Повторная регистрация с тем же email должна вернуть 409.
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

    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient) -> None:
    """
    Регистрация с невалидным email должна вернуть 422.
    """

    payload = {
        "email": "invalid-email",
        "password": "StrongPass123",
        "full_name": "Invalid Email",
    }

    response = await client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient) -> None:
    """
    Пароль без заглавной буквы или цифры должен вернуть 422.
    """

    payload = {
        "email": "weak@test.com",
        "password": "weakpassword",
        "full_name": "Weak Password",
    }

    response = await client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient) -> None:
    """
    Пароль короче 8 символов должен вернуть 422.
    """

    payload = {
        "email": "short@test.com",
        "password": "Abc12",
        "full_name": "Short Password",
    }

    response = await client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    assert response.status_code == 422


# ============================================================================
# Login Tests
# ============================================================================

@pytest.mark.asyncio
async def test_login_success(
    client: AsyncClient,
    student_user,
) -> None:
    """
    Успешный логин пользователя.
    """

    payload = {
        "email": student_user.email,
        "password": "Student123",
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=payload,
    )

    data = response.json()

    assert response.status_code == 200

    # Проверяем наличие токенов
    assert "access_token" in data
    assert "refresh_token" in data
    assert "token_type" in data

    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)


@pytest.mark.asyncio
async def test_login_wrong_password(
    client: AsyncClient,
    student_user,
) -> None:
    """
    Неверный пароль должен вернуть 401.
    """

    payload = {
        "email": student_user.email,
        "password": "WrongPassword123",
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=payload,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(
    client: AsyncClient,
) -> None:
    """
    Логин с несуществующим email должен вернуть 401.
    """

    payload = {
        "email": "missing@test.com",
        "password": "StrongPass123",
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=payload,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_bearer_type(
    client: AsyncClient,
    student_user,
) -> None:
    """
    token_type должен быть bearer.
    """

    payload = {
        "email": student_user.email,
        "password": "Student123",
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=payload,
    )

    data = response.json()

    assert response.status_code == 200
    assert data["token_type"] == "bearer"


# ============================================================================
# Refresh Token Tests
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_success(
    client: AsyncClient,
    student_user,
) -> None:
    """
    Успешное обновление access/refresh токенов.
    """

    # Сначала логинимся
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": student_user.email,
            "password": "Student123",
        },
    )

    login_data = login_response.json()

    refresh_token = login_data["refresh_token"]

    # Обновляем токены
    response = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    data = response.json()

    assert response.status_code == 200

    # Проверяем новую пару токенов
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Токены должны быть строками
    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)


@pytest.mark.asyncio
async def test_refresh_invalid_token(
    client: AsyncClient,
) -> None:
    """
    Невалидный refresh token должен вернуть 401.
    """

    response = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": "invalid-token",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token(
    client: AsyncClient,
    student_user,
) -> None:
    """
    Передача access token вместо refresh token должна вернуть 401.
    """

    # Создаём access token
    access_token = create_access_token(student_user.email)

    response = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": access_token,
        },
    )

    assert response.status_code == 401