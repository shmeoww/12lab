# tests/test_testik.py
#
# Дополнительные тесты для повышения покрытия с 86% до 90%+.
# Фокус на непокрытых ветках:
#   - certificates.py: retry при IntegrityError (_MAX_CERT_NUMBER_RETRIES)
#   - certificates.py: student_name = email (когда full_name is None)
#   - certificates.py: issue certificate 400 (not completed)
#   - enrollments.py: enroll on unpublished course → 400
#   - courses.py:     create/update integrity error branches
#   - analytics.py:  get_platform_stats, top_courses, my_stats (avg_score = None)
#   - auth.py:       refresh → user deleted after token issued
#   - auth.py:       TokenDecodeError fallback в dependencies
#   - tests.py:      _recalculate_progress (100%) → is_completed = True
#   - lessons.py:    update_lesson IntegrityError

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.auth.security import create_access_token, hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.certificate import Certificate
from app.models.lesson import Lesson
from app.models.test import Test
from app.models.user import User


# ============================================================================
# Helpers
# ============================================================================

async def get_token(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return resp.json()["access_token"]


# ============================================================================
# Fixtures
# ============================================================================

import pytest_asyncio


@pytest_asyncio.fixture
async def course_pub(db_session: AsyncSession, admin_user: User) -> Course:
    c = Course(
        title="Boost Course Published",
        description="desc",
        is_published=True,
        owner_id=admin_user.id,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def course_draft(db_session: AsyncSession, admin_user: User) -> Course:
    c = Course(
        title="Boost Course Draft",
        description="desc",
        is_published=False,
        owner_id=admin_user.id,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def enrolled_student(
    db_session: AsyncSession, student_user: User, course_pub: Course
) -> Enrollment:
    e = Enrollment(user_id=student_user.id, course_id=course_pub.id)
    db_session.add(e)
    await db_session.commit()
    await db_session.refresh(e)
    return e


@pytest_asyncio.fixture
async def completed_enrollment(
    db_session: AsyncSession, student_user: User, course_pub: Course
) -> Enrollment:
    e = Enrollment(
        user_id=student_user.id,
        course_id=course_pub.id,
        progress=100.0,
        is_completed=True,
    )
    db_session.add(e)
    await db_session.commit()
    await db_session.refresh(e)
    return e


@pytest_asyncio.fixture
async def lesson_in_course(
    db_session: AsyncSession, course_pub: Course
) -> Lesson:
    l = Lesson(title="Lesson1", content="content", order=1, course_id=course_pub.id)
    db_session.add(l)
    await db_session.commit()
    await db_session.refresh(l)
    return l


# ============================================================================
# certificates.py — ветка: курс не завершён → 400
# ============================================================================

@pytest.mark.asyncio
async def test_issue_cert_not_completed(
    client: AsyncClient,
    student_token: str,
    enrolled_student: Enrollment,
    course_pub: Course,
) -> None:
    """Сертификат нельзя получить, если курс не завершён → 400."""
    response = await client.post(
        f"/api/v1/certificates/{course_pub.id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 400
    assert "прогресс" in response.json()["detail"].lower()


# ============================================================================
# certificates.py — ветка: verify, full_name is None → student_name = email
# ============================================================================

@pytest.mark.asyncio
async def test_verify_cert_uses_email_when_no_full_name(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    course_pub: Course,
) -> None:
    """verify_certificate возвращает email, если у пользователя нет full_name."""
    # Убедимся, что full_name пустой
    student_user.full_name = None
    await db_session.commit()

    cert = Certificate(
        user_id=student_user.id,
        course_id=course_pub.id,
        certificate_number="CERT-BOOST-EMAIL",
    )
    db_session.add(cert)
    await db_session.commit()

    response = await client.get("/api/v1/certificates/CERT-BOOST-EMAIL")
    assert response.status_code == 200
    data = response.json()
    assert data["student_name"] == student_user.email


# ============================================================================
# certificates.py — ветка: retry при IntegrityError на certificate_number
# ============================================================================



# ============================================================================
# enrollments.py — ветка: запись на неопубликованный курс → 400
# ============================================================================

@pytest.mark.asyncio
async def test_enroll_unpublished_course_via_client(
    client: AsyncClient,
    student_token: str,
    course_draft: Course,
) -> None:
    """Запись на черновой курс возвращает 400."""
    response = await client.post(
        f"/api/v1/enrollments/{course_draft.id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 400


# ============================================================================
# enrollments.py — ветка: повторная запись → 409
# ============================================================================

@pytest.mark.asyncio
async def test_enroll_already_enrolled_returns_409(
    client: AsyncClient,
    student_token: str,
    enrolled_student: Enrollment,
    course_pub: Course,
) -> None:
    """Повторная запись на курс → 409."""
    response = await client.post(
        f"/api/v1/enrollments/{course_pub.id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 409


# ============================================================================
# courses.py — ветка: create_course IntegrityError → 409
# ============================================================================

@pytest.mark.asyncio
async def test_create_course_integrity_error(
    db_session: AsyncSession,
    admin_user: User,
    monkeypatch,
) -> None:
    """IntegrityError при create_course → 409."""
    from app.routers.courses import create_course
    from app.schemas.course import CourseCreate

    payload = CourseCreate(title="Test Course Title", description="D", is_published=False)

    async def bad_flush():
        raise IntegrityError("mock", {}, None)

    monkeypatch.setattr(db_session, "flush", bad_flush)
    with pytest.raises(Exception) as exc:
        await create_course(payload, db_session, admin_user)
    assert exc.value.status_code == 409


# ============================================================================
# courses.py — ветка: update_course IntegrityError → 409
# ============================================================================

@pytest.mark.asyncio
async def test_update_course_integrity_error(
    db_session: AsyncSession,
    admin_user: User,
    course_pub: Course,
    monkeypatch,
) -> None:
    """IntegrityError при update_course → 409."""
    from app.routers.courses import update_course
    from app.schemas.course import CourseUpdate

    payload = CourseUpdate(title="New Title")

    async def bad_flush():
        raise IntegrityError("mock", {}, None)

    monkeypatch.setattr(db_session, "flush", bad_flush)
    with pytest.raises(Exception) as exc:
        await update_course(course_pub.id, payload, db_session, admin_user)
    assert exc.value.status_code == 409


# ============================================================================
# courses.py — ветка: delete_course 404
# ============================================================================

@pytest.mark.asyncio
async def test_delete_course_not_found(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """Удаление несуществующего курса → 404."""
    response = await client.delete(
        "/api/v1/courses/999999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


# ============================================================================
# analytics.py — platform stats (admin)
# ============================================================================

@pytest.mark.asyncio
async def test_platform_stats_as_admin(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """GET /analytics/stats возвращает корректную структуру для admin."""
    response = await client.get(
        "/api/v1/analytics/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_users" in data
    assert "total_courses" in data
    assert "total_enrollments" in data
    assert "total_certificates" in data
    assert "total_lessons" in data


@pytest.mark.asyncio
async def test_platform_stats_forbidden_for_student(
    client: AsyncClient,
    student_token: str,
) -> None:
    """GET /analytics/stats запрещён для студентов → 403."""
    response = await client.get(
        "/api/v1/analytics/stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 403


# ============================================================================
# analytics.py — top courses (admin)
# ============================================================================

@pytest.mark.asyncio
async def test_top_courses_as_admin(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """GET /analytics/top-courses возвращает список для admin."""
    response = await client.get(
        "/api/v1/analytics/top-courses",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert "courses" in response.json()


@pytest.mark.asyncio
async def test_top_courses_forbidden_for_student(
    client: AsyncClient,
    student_token: str,
) -> None:
    """GET /analytics/top-courses запрещён для студентов → 403."""
    response = await client.get(
        "/api/v1/analytics/top-courses",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 403


# ============================================================================
# analytics.py — my-stats: average_score = None (нет тестов)
# ============================================================================

@pytest.mark.asyncio
async def test_my_stats_no_tests(
    client: AsyncClient,
    student_token: str,
) -> None:
    """my-stats возвращает average_score=None, когда тестов нет."""
    response = await client.get(
        "/api/v1/analytics/my-stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["average_score"] is None
    assert data["total_tests_taken"] == 0


# ============================================================================
# analytics.py — my-stats с реальными данными (average_score не None)
# ============================================================================

@pytest.mark.asyncio
async def test_my_stats_with_test_data(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_token: str,
    course_pub: Course,
) -> None:
    """my-stats возвращает средний балл, когда есть сданные тесты."""
    test_obj = Test(
        user_id=student_user.id,
        course_id=course_pub.id,
        score=75.0,
        passed=True,
    )
    db_session.add(test_obj)
    await db_session.commit()

    response = await client.get(
        "/api/v1/analytics/my-stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["average_score"] == 75.0
    assert data["total_tests_taken"] == 1


# ============================================================================
# auth dependencies — TokenDecodeError fallback
# ============================================================================

@pytest.mark.asyncio
async def test_token_decode_error_returns_401(
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """Базовый TokenDecodeError в get_current_user → 401."""
    from app.auth.dependencies import get_current_user
    from app.auth.security import TokenDecodeError

    def raise_decode(*args, **kwargs):
        raise TokenDecodeError("unexpected")

    monkeypatch.setattr("app.auth.dependencies.decode_token", raise_decode)
    with pytest.raises(Exception) as exc:
        await get_current_user("any.token.here", db_session)
    assert exc.value.status_code == 401


# ============================================================================
# auth.py — refresh с удалённым пользователем → 401
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_deleted_user(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
) -> None:
    """После удаления пользователя refresh-токен возвращает 401."""
    # Логинимся, получаем токены
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": student_user.email, "password": "Student123"},
    )
    refresh_token = login.json()["refresh_token"]

    # Удаляем пользователя из БД
    await db_session.delete(student_user)
    await db_session.commit()

    # Пробуем обновить токен
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401


# ============================================================================
# auth.py — refresh с access-токеном (неверный тип) → 401
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(
    client: AsyncClient,
    student_user: User,
) -> None:
    """Попытка использовать access-токен как refresh → 401."""
    access_token = create_access_token(student_user.email)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401


# ============================================================================
# tests.py — submit_test: passed=True + прогресс = 100% → is_completed
# ============================================================================

@pytest.mark.asyncio
async def test_submit_test_completes_course(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_token: str,
    course_pub: Course,
    lesson_in_course: Lesson,
) -> None:
    """Успешная сдача единственного теста завершает курс (is_completed=True)."""
    # Записываемся на курс
    enrollment = Enrollment(user_id=student_user.id, course_id=course_pub.id)
    db_session.add(enrollment)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/courses/{course_pub.id}/tests/",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"score": 90.0},
    )
    assert response.status_code == 201
    assert response.json()["passed"] is True

    await db_session.refresh(enrollment)
    assert enrollment.is_completed is True
    assert enrollment.progress == 100.0


# ============================================================================
# tests.py — _recalculate_progress: курс без уроков (total_lessons = 0)
# ============================================================================

@pytest.mark.asyncio
async def test_submit_test_no_lessons_progress_unchanged(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_token: str,
    admin_user: User,
) -> None:
    """Если в курсе нет уроков, прогресс после сдачи теста не меняется."""
    course = Course(
        title="Empty Course",
        description="no lessons",
        is_published=True,
        owner_id=admin_user.id,
    )
    db_session.add(course)
    await db_session.commit()
    await db_session.refresh(course)

    enrollment = Enrollment(user_id=student_user.id, course_id=course.id)
    db_session.add(enrollment)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/courses/{course.id}/tests/",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"score": 80.0},
    )
    assert response.status_code == 201

    await db_session.refresh(enrollment)
    assert enrollment.progress == 0.0
    assert enrollment.is_completed is False


# ============================================================================
# lessons.py — update_lesson IntegrityError (конфликт order) → 409
# ============================================================================

@pytest.mark.asyncio
async def test_update_lesson_order_conflict(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
    course_pub: Course,
    lesson_in_course: Lesson,
) -> None:
    """Обновление урока с занятым order возвращает 409."""
    # Создаём второй урок с order=2
    resp = await client.post(
        f"/api/v1/courses/{course_pub.id}/lessons/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Lesson 2", "content": "c2", "order": 2},
    )
    assert resp.status_code == 201

    # Пытаемся переставить первый урок на order=2
    response = await client.put(
        f"/api/v1/courses/{course_pub.id}/lessons/{lesson_in_course.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"order": 2},
    )
    assert response.status_code == 409


# ============================================================================
# lessons.py — delete_lesson 404
# ============================================================================

@pytest.mark.asyncio
async def test_delete_lesson_not_found(
    client: AsyncClient,
    admin_token: str,
    course_pub: Course,
) -> None:
    """Удаление несуществующего урока → 404."""
    response = await client.delete(
        f"/api/v1/courses/{course_pub.id}/lessons/999999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


# ============================================================================
# courses.py — list_courses pagination (skip, limit)
# ============================================================================

@pytest.mark.asyncio
async def test_list_courses_with_pagination(
    client: AsyncClient,
    course_pub: Course,
) -> None:
    """Пагинация курсов работает корректно."""
    response = await client.get("/api/v1/courses/?skip=0&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    assert data["limit"] == 5


# ============================================================================
# courses.py — get_course: 404 для несуществующего курса
# ============================================================================

@pytest.mark.asyncio
async def test_get_course_not_found(client: AsyncClient) -> None:
    """GET /courses/999999 → 404."""
    response = await client.get("/api/v1/courses/999999")
    assert response.status_code == 404


# ============================================================================
# certificates.py — my_certificates: пустой список
# ============================================================================

@pytest.mark.asyncio
async def test_my_certificates_empty(
    client: AsyncClient,
    student_token: str,
) -> None:
    """GET /certificates/my возвращает пустой список, если нет сертификатов."""
    response = await client.get(
        "/api/v1/certificates/my",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


# ============================================================================
# certificates.py — issue: всё ок, возвращается 201
# ============================================================================

@pytest.mark.asyncio
async def test_issue_certificate_success(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_token: str,
    course_pub: Course,
    completed_enrollment: Enrollment,
) -> None:
    """Успешная выдача сертификата → 201."""
    response = await client.post(
        f"/api/v1/certificates/{course_pub.id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["certificate_number"].startswith("CERT-")
    assert data["course_id"] == course_pub.id


# ============================================================================
# courses.py — create_course forbidden for student
# ============================================================================

@pytest.mark.asyncio
async def test_create_course_forbidden_for_student(
    client: AsyncClient,
    student_token: str,
) -> None:
    """Создание курса студентом → 403."""
    response = await client.post(
        "/api/v1/courses/",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"title": "T", "description": "D", "is_published": False},
    )
    assert response.status_code == 403


# ============================================================================
# lessons.py — get_lesson: wrong course → 404
# ============================================================================

@pytest.mark.asyncio
async def test_get_lesson_wrong_course_id(
    client: AsyncClient,
    student_token: str,
    course_pub: Course,
    lesson_in_course: Lesson,
    admin_user: User,
    db_session: AsyncSession,
) -> None:
    """Запрос урока с неверным course_id → 404."""
    # Создаём другой курс
    other = Course(
        title="Other Course",
        description="other",
        is_published=True,
        owner_id=admin_user.id,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    # Урок принадлежит course_pub, запрашиваем через other
    response = await client.get(
        f"/api/v1/courses/{other.id}/lessons/{lesson_in_course.id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 404
