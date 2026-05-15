# tests/test_lessons_analytics.py

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models import test as test_models


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
        title="Python Backend",
        description="Backend development course",
        is_published=True,
        owner_id=admin_user.id,
    )

    db_session.add(course)
    await db_session.commit()
    await db_session.refresh(course)

    yield course


@pytest_asyncio.fixture
async def lesson(
    db_session: AsyncSession,
    published_course: Course,
) -> AsyncGenerator[Lesson, None]:
    """
    Создаёт тестовый урок.
    """

    lesson_obj = Lesson(
        title="Introduction",
        content="Lesson content",
        order=1,
        course_id=published_course.id,
    )

    db_session.add(lesson_obj)
    await db_session.commit()
    await db_session.refresh(lesson_obj)

    yield lesson_obj


@pytest_asyncio.fixture
async def enrollment(
    db_session: AsyncSession,
    student_user,
    published_course: Course,
) -> AsyncGenerator[Enrollment, None]:
    """
    Создаёт запись пользователя на курс.
    """

    enrollment_obj = Enrollment(
        user_id=student_user.id,
        course_id=published_course.id,
        progress=0.0,
        is_completed=False,
    )

    db_session.add(enrollment_obj)
    await db_session.commit()
    await db_session.refresh(enrollment_obj)

    yield enrollment_obj


# ============================================================================
# Lessons Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_lessons_empty(
    client: AsyncClient,
    student_token: str,
    published_course: Course,
) -> None:
    """
    Если уроков нет — возвращается пустой список.
    """

    response = await client.get(
        f"/api/v1/courses/{published_course.id}/lessons/",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_lesson_as_admin(
    client: AsyncClient,
    admin_token: str,
    published_course: Course,
) -> None:
    """
    Администратор может создать урок.
    """

    payload = {
        "title": "New Lesson",
        "content": "Lesson body",
        "order": 1,
    }

    response = await client.post(
        f"/api/v1/courses/{published_course.id}/lessons/",
        json=payload,
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    data = response.json()

    assert response.status_code == 201

    assert data["title"] == payload["title"]
    assert data["content"] == payload["content"]
    assert data["order"] == payload["order"]


@pytest.mark.asyncio
async def test_create_lesson_as_student(
    client: AsyncClient,
    student_token: str,
    published_course: Course,
) -> None:
    """
    Студент не может создавать уроки.
    """

    payload = {
        "title": "Student Lesson",
        "content": "Forbidden",
        "order": 1,
    }

    response = await client.post(
        f"/api/v1/courses/{published_course.id}/lessons/",
        json=payload,
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_lesson_duplicate_order(
    client: AsyncClient,
    admin_token: str,
    lesson: Lesson,
    published_course: Course,
) -> None:
    """
    Два урока с одинаковым order запрещены.
    """

    payload = {
        "title": "Duplicate Order",
        "content": "Duplicate",
        "order": lesson.order,
    }

    response = await client.post(
        f"/api/v1/courses/{published_course.id}/lessons/",
        json=payload,
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_lesson_by_id(
    client: AsyncClient,
    student_token: str,
    published_course: Course,
    lesson: Lesson,
) -> None:
    """
    Получение урока по ID.
    """

    response = await client.get(
        f"/api/v1/courses/{published_course.id}/lessons/{lesson.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    data = response.json()

    assert response.status_code == 200

    assert data["id"] == lesson.id
    assert data["title"] == lesson.title


@pytest.mark.asyncio
async def test_get_lesson_wrong_course(
    client: AsyncClient,
    student_token: str,
    db_session: AsyncSession,
    admin_user,
    lesson: Lesson,
) -> None:
    """
    Урок не должен быть доступен через другой course_id.
    """

    another_course = Course(
        title="Another Course",
        description="Other course",
        is_published=True,
        owner_id=admin_user.id,
    )

    db_session.add(another_course)
    await db_session.commit()
    await db_session.refresh(another_course)

    response = await client.get(
        f"/api/v1/courses/{another_course.id}/lessons/{lesson.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_lesson_as_admin(
    client: AsyncClient,
    admin_token: str,
    published_course: Course,
    lesson: Lesson,
) -> None:
    """
    Администратор может обновить урок.
    """

    payload = {
        "title": "Updated Lesson",
        "content": "Updated content",
        "order": 2,
    }

    response = await client.put(
        f"/api/v1/courses/{published_course.id}/lessons/{lesson.id}",
        json=payload,
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    data = response.json()

    assert response.status_code == 200

    assert data["title"] == payload["title"]
    assert data["content"] == payload["content"]
    assert data["order"] == payload["order"]


@pytest.mark.asyncio
async def test_delete_lesson_as_admin(
    client: AsyncClient,
    admin_token: str,
    published_course: Course,
    lesson: Lesson,
) -> None:
    """
    Администратор может удалить урок.
    """

    response = await client.delete(
        f"/api/v1/courses/{published_course.id}/lessons/{lesson.id}",
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    assert response.status_code == 204


# ============================================================================
# Tests / Quiz Tests
# ============================================================================

@pytest.mark.asyncio
async def test_submit_test_success(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Успешная сдача теста.
    """

    payload = {
        "score": 80,
    }

    response = await client.post(
        f"/api/v1/courses/{published_course.id}/tests/",
        json=payload,
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    data = response.json()

    assert response.status_code == 201

    assert data["score"] == 80
    assert data["passed"] is True


@pytest.mark.asyncio
async def test_submit_test_fail(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Тест с низким score должен быть не пройден.
    """

    payload = {
        "score": 40,
    }

    response = await client.post(
        f"/api/v1/courses/{published_course.id}/tests/",
        json=payload,
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    data = response.json()

    assert response.status_code == 201

    assert data["score"] == 40
    assert data["passed"] is False


@pytest.mark.asyncio
async def test_submit_test_not_enrolled(
    client: AsyncClient,
    student_token: str,
    published_course: Course,
) -> None:
    """
    Нельзя сдавать тест без записи на курс.
    """

    payload = {
        "score": 90,
    }

    response = await client.post(
        f"/api/v1/courses/{published_course.id}/tests/",
        json=payload,
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_submit_test_unauthorized(
    client: AsyncClient,
    published_course: Course,
) -> None:
    """
    Без токена доступ запрещён.
    """

    payload = {
        "score": 75,
    }

    response = await client.post(
        f"/api/v1/courses/{published_course.id}/tests/",
        json=payload,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_my_test_results(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user,
    student_token: str,
    enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Получение результатов своих тестов.
    """

    test_result = test_models.Test(
        user_id=student_user.id,
        course_id=published_course.id,
        score=85,
        passed=True,
    )

    db_session.add(test_result)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/courses/{published_course.id}/tests/my",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    data = response.json()

    assert response.status_code == 200
    assert isinstance(data, list)
    assert len(data) == 1

    assert data[0]["score"] == 85
    assert data[0]["passed"] is True


@pytest.mark.asyncio
async def test_get_my_test_results_empty(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
    published_course: Course,
) -> None:
    """
    Если результатов нет — возвращается пустой список.
    """

    response = await client.get(
        f"/api/v1/courses/{published_course.id}/tests/my",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 200
    assert response.json() == []


# ============================================================================
# Analytics Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_platform_stats_as_admin(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """
    Администратор может получить статистику платформы.
    """

    response = await client.get(
        "/api/v1/analytics/stats",
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    data = response.json()

    assert response.status_code == 200

    assert "total_users" in data
    assert "total_courses" in data
    assert "total_enrollments" in data
    assert "total_certificates" in data
    assert "total_lessons" in data

@pytest.mark.asyncio
async def test_get_platform_stats_as_student(
    client: AsyncClient,
    student_token: str,
) -> None:
    """Студент не может получить статистику платформы."""
    response = await client.get(
        "/api/v1/analytics/stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_top_courses_as_admin(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """Администратор может получить топ курсов."""
    response = await client.get(
        "/api/v1/analytics/top-courses",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    data = response.json()
    assert response.status_code == 200
    assert "courses" in data
    assert isinstance(data["courses"], list)


@pytest.mark.asyncio
async def test_get_my_stats(
    client: AsyncClient,
    student_token: str,
) -> None:
    """Студент может получить свою статистику."""
    response = await client.get(
        "/api/v1/analytics/my-stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    data = response.json()
    assert response.status_code == 200
    assert "enrolled_courses" in data
    assert "completed_courses" in data
    assert "certificates_count" in data
    assert "total_tests_taken" in data


@pytest.mark.asyncio
async def test_get_my_stats_with_data(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
) -> None:
    """Статистика отражает реальные данные студента."""
    response = await client.get(
        "/api/v1/analytics/my-stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["enrolled_courses"] >= 1