"""
app/routers/enrollments.py

Роутер записи студентов на курсы.

Таблица доступа
───────────────
  POST   /enrollments/{course_id}          — записаться на курс (ActiveUser)
  GET    /enrollments/my                   — мои записи (ActiveUser)
  GET    /enrollments/{course_id}/progress — мой прогресс по курсу (ActiveUser)
  DELETE /enrollments/{course_id}          — отписаться от курса (ActiveUser) → 204

Порядок маршрутов важен!
────────────────────────
  Маршрут GET /enrollments/my должен быть зарегистрирован ДО
  GET /enrollments/{course_id}/progress — иначе FastAPI интерпретирует
  строку "my" как course_id (path-параметр) и вернёт 422.

Коды ответов
────────────
  200 OK          — успешный GET
  201 Created     — успешная запись на курс
  204 No Content  — успешная отписка
  400 Bad Request — курс не опубликован
  403 Forbidden   — нет доступа (не записан на курс)
  404 Not Found   — курс или запись не найдена
  409 Conflict    — уже записан на этот курс
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ActiveUser
from app.database import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.schemas.enrollment import EnrollmentResponse

logger = logging.getLogger(__name__)

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(
    prefix="/enrollments",
    tags=["Enrollments"],
)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ╚══════════════════════════════════════════════════════════════════════════════

async def _get_published_course_or_404(
    db: AsyncSession,
    course_id: int,
) -> Course:
    """
    Загружает опубликованный курс или бросает HTTP-исключение.

    Логика:
      - Курс не найден → 404
      - Курс найден, но не опубликован → 400 (нельзя записаться на черновик)

    Args:
        db:        Async-сессия SQLAlchemy.
        course_id: ID курса из URL.

    Returns:
        ORM-объект Course с is_published=True.

    Raises:
        HTTPException 404: курс не существует.
        HTTPException 400: курс существует, но не опубликован.
    """
    course: Course | None = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Курс с id={course_id} не найден",
        )
    if not course.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Курс с id={course_id} ещё не опубликован. Запись недоступна",
        )
    return course


async def _get_enrollment_or_404(
    db: AsyncSession,
    user_id: int,
    course_id: int,
) -> Enrollment:
    """
    Загружает запись студента на курс или бросает HTTP 404.

    Ищет по составному ключу (user_id, course_id) — уникальному по схеме БД.

    Args:
        db:        Async-сессия.
        user_id:   ID текущего пользователя.
        course_id: ID курса.

    Returns:
        ORM-объект Enrollment.

    Raises:
        HTTPException 404: запись не найдена (не записан на курс).
    """
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course_id,
        )
    )
    enrollment: Enrollment | None = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Вы не записаны на курс с id={course_id}",
        )
    return enrollment


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  POST /enrollments/{course_id} — записаться на курс
# ╚══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/{course_id}",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Записаться на курс",
    responses={
        201: {"description": "Запись на курс оформлена"},
        400: {"description": "Курс не опубликован"},
        404: {"description": "Курс не найден"},
        409: {"description": "Вы уже записаны на этот курс"},
    },
)
async def enroll_in_course(
    course_id: int,
    db: DbSession,
    current_user: ActiveUser,
) -> EnrollmentResponse:
    """
    Записывает текущего пользователя на курс.

    Шаги:
      1. Проверяем существование и статус публикации курса.
      2. Создаём запись Enrollment.
      3. При IntegrityError (UniqueConstraint) → 409: уже записан.
      4. Возвращаем EnrollmentResponse.
    """
    # Шаг 1: курс должен существовать и быть опубликован
    await _get_published_course_or_404(db, course_id)

    # Шаг 2: создаём запись (progress=0.0 и is_completed=False — из defaults модели)
    enrollment = Enrollment(
        user_id=current_user.id,
        course_id=course_id,
    )
    db.add(enrollment)

    try:
        await db.flush()
        await db.refresh(enrollment)   # подтягиваем enrolled_at из server_default
    except IntegrityError:
        # UniqueConstraint("user_id", "course_id") — повторная запись
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Вы уже записаны на курс с id={course_id}",
        )

    logger.info(
        "Пользователь id=%d записался на курс id=%d",
        current_user.id, course_id,
    )
    return EnrollmentResponse.model_validate(enrollment)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GET /enrollments/my — мои курсы
# ╚══════════════════════════════════════════════════════════════════════════════
# ВАЖНО: этот маршрут должен быть ДО /{course_id}/progress,
# иначе "my" будет перехвачено как course_id.

@router.get(
    "/my",
    response_model=list[EnrollmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Мои записи на курсы",
    description="Возвращает список всех курсов, на которые записан текущий пользователь.",
)
async def my_enrollments(
    db: DbSession,
    current_user: ActiveUser,
) -> list[EnrollmentResponse]:
    """
    Возвращает все записи текущего пользователя, отсортированные
    по дате записи (свежие первыми).
    """
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.user_id == current_user.id)
        .order_by(Enrollment.enrolled_at.desc())
    )
    enrollments = list(result.scalars().all())
    return [EnrollmentResponse.model_validate(e) for e in enrollments]


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GET /enrollments/{course_id}/progress — мой прогресс по курсу
# ╚══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{course_id}/progress",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Мой прогресс по курсу",
    responses={
        404: {"description": "Курс не найден или вы не записаны на него"},
    },
)
async def get_my_progress(
    course_id: int,
    db: DbSession,
    current_user: ActiveUser,
) -> EnrollmentResponse:
    """
    Возвращает текущий прогресс пользователя по указанному курсу.

    Прогресс обновляется автоматически после каждой успешной сдачи теста
    (через POST /courses/{course_id}/tests).
    """
    enrollment = await _get_enrollment_or_404(db, current_user.id, course_id)
    return EnrollmentResponse.model_validate(enrollment)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  DELETE /enrollments/{course_id} — отписаться от курса
# ╚══════════════════════════════════════════════════════════════════════════════

@router.delete(
    "/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отписаться от курса",
    responses={
        204: {"description": "Запись на курс удалена"},
        404: {"description": "Вы не записаны на этот курс"},
    },
)
async def unenroll_from_course(
    course_id: int,
    db: DbSession,
    current_user: ActiveUser,
) -> None:
    """
    Удаляет запись текущего пользователя на курс.

    Прогресс и история тестов НЕ удаляются — только сама запись Enrollment.
    При повторной записи на курс прогресс начнётся с нуля.

    Возвращает 204 No Content.
    """
    enrollment = await _get_enrollment_or_404(db, current_user.id, course_id)

    await db.delete(enrollment)
    await db.flush()

    logger.info(
        "Пользователь id=%d отписался от курса id=%d",
        current_user.id, course_id,
    )
