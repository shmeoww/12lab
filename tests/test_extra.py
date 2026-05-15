# tests/test_extra.py

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.enrollment import Enrollment


# ============================================================================
# Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def published_course(
    db_session: AsyncSession,
    admin_user,
) -> AsyncGenerator[Course, None]:
    """
    Создаёт опубликованный курс.
    """

    course = Course(
        title="Extra Testing Course",
        description="Course for extra tests",
        is_published=True,
        owner_id=admin_user.id,
    )

    db_session.add(course)
    await db_session.commit()
    await db_session.refresh(course)

    yield course


@pytest_asyncio.fixture
async def completed_enrollment(
    db_session: AsyncSession,
    student_user,
    published_course: Course,
) -> AsyncGenerator[Enrollment, None]:
    """
    Создаёт завершённую запись на курс.
    """

    enrollment = Enrollment(
        user_id=student_user.id,
        course_id=published_course.id,
        progress=100.0,
        is_completed=True,
    )

    db_session.add(enrollment)
    await db_session.commit()
    await db_session.refresh(enrollment)

    yield enrollment


# ============================================================================
# Certificates Tests
# ============================================================================

@pytest.mark.asyncio
async def test_verify_certificate_success(
    client: AsyncClient,
    student_token: str,
    completed_enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Проверка сертификата по certificate_number.
    """

    # Получаем сертификат
    issue_response = await client.post(
        f"/api/v1/certificates/{published_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    issue_data = issue_response.json()

    assert issue_response.status_code == 201

    certificate_number = issue_data["certificate_number"]

    # Проверяем сертификат без авторизации
    verify_response = await client.get(
        f"/api/v1/certificates/{certificate_number}"
    )

    verify_data = verify_response.json()

    assert verify_response.status_code == 200

    assert verify_data["certificate_number"] == certificate_number
    assert verify_data["course_title"] == published_course.title
    assert "student_name" in verify_data
    assert verify_data["is_valid"] is True


@pytest.mark.asyncio
async def test_verify_certificate_not_found(
    client: AsyncClient,
) -> None:
    """
    Проверка несуществующего сертификата должна вернуть 404.
    """

    response = await client.get(
        "/api/v1/certificates/CERT-9999-XXXXXXXX"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_issue_certificate_course_not_found(
    client: AsyncClient,
    student_token: str,
) -> None:
    """
    Выдача сертификата для несуществующего курса → 404.
    """

    response = await client.post(
        "/api/v1/certificates/999999",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_issue_certificate_not_enrolled(
    client: AsyncClient,
    student_token: str,
    published_course: Course,
) -> None:
    """
    Нельзя получить сертификат без записи на курс.
    """

    response = await client.post(
        f"/api/v1/certificates/{published_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 404


# ============================================================================
# Auth Tests
# ============================================================================

@pytest.mark.asyncio
async def test_register_without_full_name(
    client: AsyncClient,
) -> None:
    """
    full_name является опциональным полем.
    """

    payload = {
        "email": "nofullname@test.com",
        "password": "StrongPass123",
    }

    response = await client.post(
        "/api/v1/auth/register",
        json=payload,
    )

    data = response.json()

    assert response.status_code == 201

    assert data["email"] == payload["email"]

    # full_name может отсутствовать или быть null
    assert "full_name" in data


@pytest.mark.asyncio
async def test_login_inactive_user(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user,
) -> None:
    """
    Неактивный пользователь не может логиниться.
    """

    # Деактивируем пользователя
    student_user.is_active = False

    db_session.add(student_user)
    await db_session.commit()
    await db_session.refresh(student_user)

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": student_user.email,
            "password": "Student123",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_refresh_success_returns_new_tokens(
    client: AsyncClient,
    student_user,
) -> None:
    """
    После refresh должны возвращаться новые токены.
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

    old_access_token = login_data["access_token"]
    old_refresh_token = login_data["refresh_token"]

    # Refresh
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    refresh_data = refresh_response.json()

    assert refresh_response.status_code == 200

    # Новые токены должны отличаться
    assert refresh_data["access_token"] != old_access_token
    assert refresh_data["refresh_token"] != old_refresh_token


# ============================================================================
# Courses Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_unpublished_course_by_id(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_user,
) -> None:
    """
    GET /courses/{id} возвращает курс даже если он неопубликован.
    Список GET /courses/ показывает только опубликованные,
    но детали конкретного курса доступны всегда.
    """

    course = Course(
        title="Draft Course",
        description="Hidden course",
        is_published=False,
        owner_id=admin_user.id,
    )

    db_session.add(course)
    await db_session.commit()
    await db_session.refresh(course)

    response = await client.get(
        f"/api/v1/courses/{course.id}"
    )

    assert response.status_code == 200
    assert response.json()["is_published"] is False


@pytest.mark.asyncio
async def test_update_course_partial(
    client: AsyncClient,
    admin_token: str,
    published_course: Course,
) -> None:
    """
    Частичное обновление курса не должно менять остальные поля.
    """

    original_title = published_course.title
    original_description = published_course.description

    payload = {
        "is_published": False,
    }

    response = await client.put(
        f"/api/v1/courses/{published_course.id}",
        json=payload,
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    data = response.json()

    assert response.status_code == 200

    # Изменилось только поле is_published
    assert data["is_published"] is False
    assert data["title"] == original_title
    assert data["description"] == original_description


# ============================================================================
# Enrollments Tests
# ============================================================================

@pytest.mark.asyncio
async def test_enroll_nonexistent_course(
    client: AsyncClient,
    student_token: str,
) -> None:
    """
    Запись на несуществующий курс должна вернуть 404.
    """

    response = await client.post(
        "/api/v1/enrollments/999999",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_progress_not_enrolled(
    client: AsyncClient,
    student_token: str,
    published_course: Course,
) -> None:
    """
    Получение прогресса без записи на курс должно вернуть 404.
    """

    response = await client.get(
        f"/api/v1/enrollments/{published_course.id}/progress",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 404