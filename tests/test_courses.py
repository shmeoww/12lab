# tests/test_courses.py

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course


# ============================================================================
# Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def course(
    db_session: AsyncSession,
    admin_user,          
) -> AsyncGenerator[Course, None]:
    new_course = Course(
        title="Python Advanced",
        description="Advanced Python course",
        is_published=True,
        owner_id=admin_user.id,  
    )
    db_session.add(new_course)
    await db_session.commit()
    await db_session.refresh(new_course)
    yield new_course


@pytest_asyncio.fixture
async def unpublished_course(
    db_session: AsyncSession,
    admin_user,     
) -> AsyncGenerator[Course, None]:
    new_course = Course(
        title="Hidden Course",
        description="Draft course",
        is_published=False,
        owner_id=admin_user.id,  
    )
    db_session.add(new_course)          # ← этого не хватало
    await db_session.commit()           # ← этого не хватало
    await db_session.refresh(new_course)  # ← этого не хватало
    yield new_course  

# ============================================================================
# Get Courses Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_courses_empty(
    client: AsyncClient,
) -> None:
    """
    Если курсов нет — должен вернуться пустой список.
    """
    response = await client.get("/api/v1/courses/")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_get_courses_returns_only_published(
    client: AsyncClient,
    course: Course,
    unpublished_course: Course,
) -> None:
    """
    GET /courses/ должен возвращать только опубликованные курсы.
    """

    response = await client.get("/api/v1/courses/")

    data = response.json()
    courses = data["items"]   # было data
    assert isinstance(courses, list)
    assert len(courses) == 1
    assert courses[0]["id"] == course.id
    assert courses[0]["is_published"] is True


@pytest.mark.asyncio
async def test_get_course_by_id(
    client: AsyncClient,
    course: Course,
) -> None:
    """
    Получение курса по ID.
    """

    response = await client.get(
        f"/api/v1/courses/{course.id}"
    )

    data = response.json()

    assert response.status_code == 200

    assert data["id"] == course.id
    assert data["title"] == course.title
    assert data["description"] == course.description


@pytest.mark.asyncio
async def test_get_course_not_found(
    client: AsyncClient,
) -> None:
    """
    Несуществующий курс должен вернуть 404.
    """

    response = await client.get(
        "/api/v1/courses/999999"
    )

    assert response.status_code == 404


# ============================================================================
# Create Course Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_course_as_admin(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """
    Администратор может создать курс.
    """

    payload = {
        "title": "FastAPI Mastery",
        "description": "Learn FastAPI deeply",
        "is_published": True,
    }

    response = await client.post(
        "/api/v1/courses/",
        json=payload,
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    data = response.json()

    assert response.status_code == 201

    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["is_published"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_course_as_student(
    client: AsyncClient,
    student_token: str,
) -> None:
    """
    Студент не может создавать курсы.
    """

    payload = {
        "title": "Unauthorized Course",
        "description": "Students cannot create courses",
    }

    response = await client.post(
        "/api/v1/courses/",
        json=payload,
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_course_unauthorized(
    client: AsyncClient,
) -> None:
    """
    Без токена создание курса запрещено.
    """

    payload = {
        "title": "No Auth Course",
        "description": "Unauthorized",
    }

    response = await client.post(
        "/api/v1/courses/",
        json=payload,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_course_short_title(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """
    Title меньше 3 символов должен вернуть 422.
    """

    payload = {
        "title": "Py",
        "description": "Too short",
    }

    response = await client.post(
        "/api/v1/courses/",
        json=payload,
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    assert response.status_code == 422


# ============================================================================
# Update Course Tests
# ============================================================================

@pytest.mark.asyncio
async def test_update_course_as_admin(
    client: AsyncClient,
    admin_token: str,
    course: Course,
) -> None:
    """
    Администратор может обновить курс.
    """

    payload = {
        "title": "Updated Python Course",
        "description": "Updated description",
        "is_published": False,
    }

    response = await client.put(
        f"/api/v1/courses/{course.id}",
        json=payload,
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    data = response.json()

    assert response.status_code == 200

    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["is_published"] is False


@pytest.mark.asyncio
async def test_update_course_not_found(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """
    Обновление несуществующего курса должно вернуть 404.
    """

    payload = {
        "title": "Missing Course",
        "description": "Not found",
        "is_published": True,
    }

    response = await client.put(
        "/api/v1/courses/999999",
        json=payload,
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_course_as_student(
    client: AsyncClient,
    student_token: str,
    course: Course,
) -> None:
    """
    Студент не может обновлять курсы.
    """

    payload = {
        "title": "Hacked Course",
        "description": "Students cannot edit",
        "is_published": True,
    }

    response = await client.put(
        f"/api/v1/courses/{course.id}",
        json=payload,
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 403


# ============================================================================
# Delete Course Tests
# ============================================================================

@pytest.mark.asyncio
async def test_delete_course_as_admin(
    client: AsyncClient,
    admin_token: str,
    course: Course,
) -> None:
    """
    Администратор может удалить курс.
    """

    response = await client.delete(
        f"/api/v1/courses/{course.id}",
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    assert response.status_code == 204

    # Проверяем что курс действительно удалён
    get_response = await client.get(
        f"/api/v1/courses/{course.id}"
    )

    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_course_as_student(
    client: AsyncClient,
    student_token: str,
    course: Course,
) -> None:
    """
    Студент не может удалять курсы.
    """

    response = await client.delete(
        f"/api/v1/courses/{course.id}",
        headers={
            "Authorization": f"Bearer {student_token}"
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_course_not_found(
    client: AsyncClient,
    admin_token: str,
) -> None:
    """
    Удаление несуществующего курса должно вернуть 404.
    """

    response = await client.delete(
        "/api/v1/courses/999999",
        headers={
            "Authorization": f"Bearer {admin_token}"
        },
    )

    assert response.status_code == 404