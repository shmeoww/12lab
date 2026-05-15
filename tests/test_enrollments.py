# tests/test_enrollments.py

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.certificate import Certificate
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
        title="Published Course",
        description="Public course",
        is_published=True,
        owner_id=admin_user.id,
    )

    db_session.add(course)
    await db_session.commit()
    await db_session.refresh(course)

    yield course


@pytest_asyncio.fixture
async def unpublished_course(
    db_session: AsyncSession,
    admin_user,
) -> AsyncGenerator[Course, None]:
    """
    Создаёт неопубликованный курс.
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

    yield course


@pytest_asyncio.fixture
async def enrollment(
    db_session: AsyncSession,
    student_user,
    published_course: Course,
) -> AsyncGenerator[Enrollment, None]:
    """
    Создаёт запись пользователя на курс.
    """

    enroll = Enrollment(
        user_id=student_user.id,
        course_id=published_course.id,
        progress=0.0,
        is_completed=False,
    )

    db_session.add(enroll)
    await db_session.commit()
    await db_session.refresh(enroll)

    yield enroll


@pytest_asyncio.fixture
async def completed_enrollment(
    db_session: AsyncSession,
    student_user,
    published_course: Course,
) -> AsyncGenerator[Enrollment, None]:
    """
    Создаёт завершённую запись на курс.
    """

    enroll = Enrollment(
        user_id=student_user.id,
        course_id=published_course.id,
        progress=100.0,
        is_completed=True,
    )

    db_session.add(enroll)
    await db_session.commit()
    await db_session.refresh(enroll)

    yield enroll


# ============================================================================
# Enrollment Tests
# ============================================================================

@pytest.mark.asyncio
async def test_enroll_success(
    client: AsyncClient,
    student_token: str,
    published_course: Course,
) -> None:
    """
    Студент может записаться на опубликованный курс.
    """

    response = await client.post(
        f"/api/v1/enrollments/{published_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    data = response.json()

    assert response.status_code == 201

    assert data["course_id"] == published_course.id
    assert data["progress"] == 0.0
    assert data["is_completed"] is False


@pytest.mark.asyncio
async def test_enroll_duplicate(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Повторная запись на курс должна вернуть 409.
    """

    response = await client.post(
        f"/api/v1/enrollments/{published_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_enroll_unpublished_course(
    client: AsyncClient,
    student_token: str,
    unpublished_course: Course,
) -> None:
    """
    Нельзя записаться на неопубликованный курс.
    """

    response = await client.post(
        f"/api/v1/enrollments/{unpublished_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_enroll_unauthorized(
    client: AsyncClient,
    published_course: Course,
) -> None:
    """
    Без токена запись на курс запрещена.
    """

    response = await client.post(
        f"/api/v1/enrollments/{published_course.id}"
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_my_enrollments(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
) -> None:
    """
    Получение списка своих записей.
    """

    response = await client.get(
        "/api/v1/enrollments/my",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    data = response.json()

    assert response.status_code == 200
    assert isinstance(data, list)
    assert len(data) == 1

    assert data[0]["course_id"] == enrollment.course_id


@pytest.mark.asyncio
async def test_get_my_enrollments_empty(
    client: AsyncClient,
    student_token: str,
) -> None:
    """
    Если записей нет — должен вернуться пустой список.
    """

    response = await client.get(
        "/api/v1/enrollments/my",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_progress(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Получение прогресса по курсу.
    """

    response = await client.get(
        f"/api/v1/enrollments/{published_course.id}/progress",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    data = response.json()

    assert response.status_code == 200

    assert data["course_id"] == published_course.id
    assert data["progress"] == enrollment.progress
    assert data["is_completed"] == enrollment.is_completed


@pytest.mark.asyncio
async def test_unenroll_success(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Успешная отписка от курса.
    """

    response = await client.delete(
        f"/api/v1/enrollments/{published_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_unenroll_not_enrolled(
    client: AsyncClient,
    student_token: str,
    published_course: Course,
) -> None:
    """
    Отписка без существующей записи должна вернуть 404.
    """

    response = await client.delete(
        f"/api/v1/enrollments/{published_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 404


# ============================================================================
# Certificate Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_certificate_not_completed(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Нельзя получить сертификат если курс не завершён.
    """

    response = await client.post(
        f"/api/v1/certificates/{published_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_certificate_success(
    client: AsyncClient,
    student_token: str,
    completed_enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Успешное получение сертификата.
    """

    response = await client.post(
        f"/api/v1/certificates/{published_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    data = response.json()

    assert response.status_code == 201

    assert data["course_id"] == published_course.id
    assert "id" in data
    assert "issued_at" in data


@pytest.mark.asyncio
async def test_get_certificate_duplicate(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user,
    student_token: str,
    completed_enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Повторное получение сертификата должно вернуть 409.
    """

    certificate = Certificate(
        user_id=student_user.id,
        course_id=published_course.id,
        certificate_number="CERT-2024-TEST0001",
    )

    db_session.add(certificate)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/certificates/{published_course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_my_certificates_empty(
    client: AsyncClient,
    student_token: str,
) -> None:
    """
    Если сертификатов нет — возвращается пустой список.
    """

    response = await client.get(
        "/api/v1/certificates/my",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_my_certificates(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user,
    student_token: str,
    published_course: Course,
) -> None:
    """
    Получение списка сертификатов пользователя.
    """

    certificate = Certificate(
        user_id=student_user.id,
        course_id=published_course.id,
        certificate_number="CERT-2024-TEST0002",
    )

    db_session.add(certificate)
    await db_session.commit()
    await db_session.refresh(certificate)

    response = await client.get(
        "/api/v1/certificates/my",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    data = response.json()

    assert response.status_code == 200
    assert isinstance(data, list)
    assert len(data) == 1

    assert data[0]["course_id"] == published_course.id