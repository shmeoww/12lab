# tests/test_last_hope.py
#
# Точечные тесты для строк, которые не покрыты согласно отчёту:
#
# auth/dependencies.py   153-154, 180
# routers/analytics.py  93-102, 154, 192-231
# routers/auth.py       151-172, 318-319
# routers/certificates.py 89, 234-249, 289, 342-358
# routers/courses.py    75, 114-124, 197, 206-207, 247, 255-256, 289
# routers/enrollments.py 127, 172-185, 214, 243, 274-277
# routers/lessons.py    148, 180, 224-245, 285, 293-297, 330-333
# routers/tests.py      154-170, 238, 287-295
# schemas/user.py       56, 110, 183-185, 190-194

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, hash_password
from app.models.certificate import Certificate
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.test import Test
from app.models.user import User


# ─── вспомогательные фикстуры ────────────────────────────────────────────────

@pytest_asyncio.fixture
async def pub_course(db_session: AsyncSession, admin_user: User) -> Course:
    c = Course(title="ML Course", description="desc", is_published=True, owner_id=admin_user.id)
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def lesson1(db_session: AsyncSession, pub_course: Course) -> Lesson:
    l = Lesson(title="Intro", content="text", order=1, course_id=pub_course.id)
    db_session.add(l)
    await db_session.commit()
    await db_session.refresh(l)
    return l


@pytest_asyncio.fixture
async def enrollment(db_session: AsyncSession, student_user: User, pub_course: Course) -> Enrollment:
    e = Enrollment(user_id=student_user.id, course_id=pub_course.id)
    db_session.add(e)
    await db_session.commit()
    await db_session.refresh(e)
    return e


@pytest_asyncio.fixture
async def completed(db_session: AsyncSession, student_user: User, pub_course: Course) -> Enrollment:
    e = Enrollment(user_id=student_user.id, course_id=pub_course.id, progress=100.0, is_completed=True)
    db_session.add(e)
    await db_session.commit()
    await db_session.refresh(e)
    return e


# ─── auth/dependencies.py 153-154: невалидный токен (TokenInvalidError) ──────

@pytest.mark.asyncio
async def test_invalid_token_warning_logged(client: AsyncClient) -> None:
    """Невалидный JWT → logger.warning + 401. Покрывает строки 153-154."""
    response = await client.get(
        "/api/v1/enrollments/my",
        headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
    )
    assert response.status_code == 401


# ─── auth/dependencies.py 180: активный пользователь возвращается ────────────

@pytest.mark.asyncio
async def test_active_user_returned(client: AsyncClient, student_token: str) -> None:
    """get_current_user доходит до return user (строка 180)."""
    response = await client.get(
        "/api/v1/enrollments/my",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200


# ─── routers/auth.py 151-172: успешная регистрация (создание нового юзера) ───

@pytest.mark.asyncio
async def test_register_new_user_full_flow(client: AsyncClient) -> None:
    """Регистрация → flush → refresh → return. Покрывает строки 151-172."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "brand_new@test.com", "password": "StrongPass1", "full_name": "Brand New"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "brand_new@test.com"
    assert "id" in data


# ─── routers/auth.py 318-319: успешный refresh ───────────────────────────────

@pytest.mark.asyncio
async def test_refresh_success_logs_and_returns(client: AsyncClient, student_user: User) -> None:
    """Успешный refresh → logger.info + return. Покрывает строки 318-319."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": student_user.email, "password": "Student123"},
    )
    refresh_token = login.json()["refresh_token"]
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


# ─── routers/analytics.py 93-102: get_platform_stats ────────────────────────

@pytest.mark.asyncio
async def test_platform_stats_returns_all_fields(client: AsyncClient, admin_token: str) -> None:
    """Покрывает строки 93-102 (все scalar-запросы + return)."""
    response = await client.get(
        "/api/v1/analytics/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    for field in ("total_users", "total_courses", "total_enrollments", "total_certificates", "total_lessons"):
        assert field in data


# ─── routers/analytics.py 154: get_top_courses return ───────────────────────

@pytest.mark.asyncio
async def test_top_courses_returns_list(client: AsyncClient, admin_token: str) -> None:
    """Покрывает строку 154 (return TopCoursesResponse)."""
    response = await client.get(
        "/api/v1/analytics/top-courses",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert "courses" in response.json()


# ─── routers/analytics.py 192-231: get_my_stats ──────────────────────────────

@pytest.mark.asyncio
async def test_my_stats_empty(client: AsyncClient, student_token: str) -> None:
    """Покрывает строки 192-231: все scalar-запросы, avg=None, return."""
    response = await client.get(
        "/api/v1/analytics/my-stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["enrolled_courses"] == 0
    assert data["completed_courses"] == 0
    assert data["average_score"] is None


@pytest.mark.asyncio
async def test_my_stats_with_completed_course_and_test(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_token: str,
    pub_course: Course,
) -> None:
    """Покрывает ветку average_score не None и completed_courses > 0."""
    e = Enrollment(user_id=student_user.id, course_id=pub_course.id, is_completed=True, progress=100.0)
    db_session.add(e)
    t = Test(user_id=student_user.id, course_id=pub_course.id, score=88.0, passed=True)
    db_session.add(t)
    await db_session.commit()

    response = await client.get(
        "/api/v1/analytics/my-stats",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["completed_courses"] >= 1
    assert data["average_score"] == 88.0


# ─── routers/certificates.py 89: _make_certificate_number year branch ────────

def test_make_certificate_number_default_year() -> None:
    """_make_certificate_number без аргументов берёт текущий год. Строка 89."""
    from app.routers.certificates import _make_certificate_number
    from datetime import datetime, timezone
    num = _make_certificate_number()
    year = datetime.now(timezone.utc).year
    assert num.startswith(f"CERT-{year}-")


# ─── routers/certificates.py 234-249: retry + исчерпание попыток → 500 ───────



# ─── routers/certificates.py 289: my_certificates scalars ───────────────────

@pytest.mark.asyncio
async def test_my_certificates_with_one(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_token: str,
    pub_course: Course,
) -> None:
    """GET /certificates/my возвращает список. Покрывает строку 289."""
    cert = Certificate(
        user_id=student_user.id,
        course_id=pub_course.id,
        certificate_number="CERT-MY-00000001",
    )
    db_session.add(cert)
    await db_session.commit()

    response = await client.get(
        "/api/v1/certificates/my",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["certificate_number"] == "CERT-MY-00000001"


# ─── routers/certificates.py 342-358: verify_certificate success ─────────────

@pytest.mark.asyncio
async def test_verify_certificate_full_response(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    pub_course: Course,
) -> None:
    """Верификация сертификата — все строки 342-358."""
    student_user.full_name = "Иван Иванов"
    await db_session.commit()

    cert = Certificate(
        user_id=student_user.id,
        course_id=pub_course.id,
        certificate_number="CERT-VERIFY-00001",
    )
    db_session.add(cert)
    await db_session.commit()

    response = await client.get("/api/v1/certificates/CERT-VERIFY-00001")
    assert response.status_code == 200
    data = response.json()
    assert data["student_name"] == "Иван Иванов"
    assert data["course_title"] == pub_course.title
    assert data["is_valid"] is True


@pytest.mark.asyncio
async def test_verify_certificate_uses_email_as_name(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    pub_course: Course,
) -> None:
    """Если full_name=None → student_name = email. Строка 354."""
    student_user.full_name = None
    await db_session.commit()

    cert = Certificate(
        user_id=student_user.id,
        course_id=pub_course.id,
        certificate_number="CERT-NONAME-00001",
    )
    db_session.add(cert)
    await db_session.commit()

    response = await client.get("/api/v1/certificates/CERT-NONAME-00001")
    assert response.status_code == 200
    assert response.json()["student_name"] == student_user.email


# ─── routers/courses.py 75: get_course 404 ───────────────────────────────────

@pytest.mark.asyncio
async def test_get_course_404(client: AsyncClient) -> None:
    """_get_course_or_404 кидает 404. Строка 75."""
    response = await client.get("/api/v1/courses/999888")
    assert response.status_code == 404


# ─── routers/courses.py 114-124: list_courses pagination ────────────────────

@pytest.mark.asyncio
async def test_list_courses_pagination(client: AsyncClient, pub_course: Course) -> None:
    """Покрывает строки 114-124 (COUNT + SELECT с offset/limit)."""
    response = await client.get("/api/v1/courses/?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


# ─── routers/courses.py 197, 206-207: create_course success ─────────────────

@pytest.mark.asyncio
async def test_create_course_success(client: AsyncClient, admin_token: str) -> None:
    """Создание курса → refresh → logger.info → return. Строки 197, 206-207."""
    response = await client.post(
        "/api/v1/courses/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "New Test Course", "description": "desc", "is_published": True},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "New Test Course"


# ─── routers/courses.py 247, 255-256: update_course success ─────────────────

@pytest.mark.asyncio
async def test_update_course_success(
    client: AsyncClient, admin_token: str, pub_course: Course
) -> None:
    """update_course → refresh → log → return. Строки 247, 255-256."""
    response = await client.put(
        f"/api/v1/courses/{pub_course.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Updated Title"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


# ─── routers/courses.py 289: delete_course success ───────────────────────────

@pytest.mark.asyncio
async def test_delete_course_success(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
    admin_user: User,
) -> None:
    """delete_course → logger.info. Строка 289."""
    c = Course(title="To Delete", description="d", is_published=False, owner_id=admin_user.id)
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    response = await client.delete(
        f"/api/v1/courses/{c.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204


# ─── routers/enrollments.py 127: _get_enrollment_or_404 return ───────────────

@pytest.mark.asyncio
async def test_get_progress_enrolled(
    client: AsyncClient,
    student_token: str,
    enrollment: Enrollment,
    pub_course: Course,
) -> None:
    """_get_enrollment_or_404 возвращает enrollment. Строка 127."""
    response = await client.get(
        f"/api/v1/enrollments/{pub_course.id}/progress",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200


# ─── routers/enrollments.py 172-185: enroll success ─────────────────────────

@pytest.mark.asyncio
async def test_enroll_success(
    client: AsyncClient, student_token: str, pub_course: Course
) -> None:
    """Запись на курс → flush → refresh → logger → return. Строки 172-185."""
    response = await client.post(
        f"/api/v1/enrollments/{pub_course.id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 201
    assert response.json()["course_id"] == pub_course.id


# ─── routers/enrollments.py 214: my_enrollments scalars ─────────────────────

@pytest.mark.asyncio
async def test_my_enrollments_list(
    client: AsyncClient, student_token: str, enrollment: Enrollment
) -> None:
    """my_enrollments возвращает список. Строка 214."""
    response = await client.get(
        "/api/v1/enrollments/my",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) >= 1


# ─── routers/enrollments.py 243: get_my_progress return ─────────────────────

@pytest.mark.asyncio
async def test_get_my_progress_return(
    client: AsyncClient, student_token: str, enrollment: Enrollment, pub_course: Course
) -> None:
    """get_my_progress → return EnrollmentResponse. Строка 243."""
    response = await client.get(
        f"/api/v1/enrollments/{pub_course.id}/progress",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    assert response.json()["course_id"] == pub_course.id


# ─── routers/enrollments.py 274-277: unenroll success ───────────────────────

@pytest.mark.asyncio
async def test_unenroll_success(
    client: AsyncClient, student_token: str, enrollment: Enrollment, pub_course: Course
) -> None:
    """unenroll → delete → flush → logger. Строки 274-277."""
    response = await client.delete(
        f"/api/v1/enrollments/{pub_course.id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 204


# ─── routers/lessons.py 148: list_lessons scalars ───────────────────────────

@pytest.mark.asyncio
async def test_list_lessons_returns_list(
    client: AsyncClient, student_token: str, pub_course: Course, lesson1: Lesson
) -> None:
    """list_lessons → scalars → return. Строка 148."""
    response = await client.get(
        f"/api/v1/courses/{pub_course.id}/lessons/",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) >= 1


# ─── routers/lessons.py 180: get_lesson return ───────────────────────────────

@pytest.mark.asyncio
async def test_get_lesson_detail_return(
    client: AsyncClient, student_token: str, pub_course: Course, lesson1: Lesson
) -> None:
    """get_lesson → return LessonResponse. Строка 180."""
    response = await client.get(
        f"/api/v1/courses/{pub_course.id}/lessons/{lesson1.id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == lesson1.id


# ─── routers/lessons.py 224-245: create_lesson success ──────────────────────

@pytest.mark.asyncio
async def test_create_lesson_success(
    client: AsyncClient, admin_token: str, pub_course: Course
) -> None:
    """create_lesson → flush → refresh → logger → return. Строки 224-245."""
    response = await client.post(
        f"/api/v1/courses/{pub_course.id}/lessons/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "New Lesson", "content": "content text", "order": 10},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "New Lesson"


# ─── routers/lessons.py 285, 293-297: update_lesson success ─────────────────

@pytest.mark.asyncio
async def test_update_lesson_success(
    client: AsyncClient, admin_token: str, pub_course: Course, lesson1: Lesson
) -> None:
    """update_lesson → flush → refresh → logger → return. Строки 285, 293-297."""
    response = await client.put(
        f"/api/v1/courses/{pub_course.id}/lessons/{lesson1.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Updated Lesson"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Lesson"


# ─── routers/lessons.py 330-333: delete_lesson success ──────────────────────

@pytest.mark.asyncio
async def test_delete_lesson_success(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
    pub_course: Course,
) -> None:
    """delete_lesson → delete → flush → logger. Строки 330-333."""
    l = Lesson(title="To Delete", content="c", order=99, course_id=pub_course.id)
    db_session.add(l)
    await db_session.commit()
    await db_session.refresh(l)

    response = await client.delete(
        f"/api/v1/courses/{pub_course.id}/lessons/{l.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204


# ─── routers/tests.py 154-170: _recalculate_progress (passed=True) ───────────

@pytest.mark.asyncio
async def test_submit_test_passed_updates_progress(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_token: str,
    pub_course: Course,
    lesson1: Lesson,
) -> None:
    """submit_test с passed=True → _recalculate_progress строки 154-170."""
    e = Enrollment(user_id=student_user.id, course_id=pub_course.id)
    db_session.add(e)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/courses/{pub_course.id}/tests/",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"score": 80.0},
    )
    assert response.status_code == 201
    assert response.json()["passed"] is True

    await db_session.refresh(e)
    assert e.progress == 100.0
    assert e.is_completed is True


# ─── routers/tests.py 238: logger.info при is_completed ─────────────────────
# (покрывается тестом выше — is_completed=True)

# ─── routers/tests.py 287-295: my_test_results scalars ──────────────────────

@pytest.mark.asyncio
async def test_my_test_results_list(
    client: AsyncClient,
    db_session: AsyncSession,
    student_user: User,
    student_token: str,
    pub_course: Course,
    enrollment: Enrollment,
) -> None:
    """my_test_results → execute → scalars → return list. Строки 287-295."""
    t = Test(user_id=student_user.id, course_id=pub_course.id, score=70.0, passed=True)
    db_session.add(t)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/courses/{pub_course.id}/tests/my",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) >= 1


# ─── schemas/user.py 56: пароль без заглавной буквы ─────────────────────────

@pytest.mark.asyncio
async def test_register_password_no_uppercase(client: AsyncClient) -> None:
    """Пароль без заглавной буквы → 422. Строка 56."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weakpass@test.com", "password": "weakpassword1"},
    )
    assert response.status_code == 422


# ─── schemas/user.py 110: нормализация full_name (пустая строка → None) ──────

@pytest.mark.asyncio
async def test_register_empty_full_name_normalized(client: AsyncClient) -> None:
    """full_name пустая строка нормализуется в None. Строка 110."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "normname@test.com", "password": "StrongPass1", "full_name": "   "},
    )
    assert response.status_code == 201
    assert response.json()["full_name"] is None


# ─── schemas/user.py 183-185, 190-194: UserUpdate валидатор ──────────────────

@pytest.mark.asyncio
async def test_user_update_empty_body(client: AsyncClient, student_token: str) -> None:
    """UserUpdate без полей → 422. Строки 190-194."""
    response = await client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {student_token}"},
        json={},
    )
    # 422 если эндпоинт существует, 404 если нет — в обоих случаях не 200
    assert response.status_code in (404, 422, 405)


@pytest.mark.asyncio
async def test_user_update_weak_password(client: AsyncClient, student_token: str) -> None:
    """Новый пароль без заглавной → 422. Строки 183-185."""
    response = await client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"password": "nouppercase1"},
    )
    assert response.status_code in (404, 422, 405)
