"""
app/routers/courses.py

CRUD-роутер для курсов платформы онлайн-обучения.

Таблица доступа
───────────────
  GET  /courses           — публичный список опубликованных курсов (без авторизации)
  GET  /courses/{id}      — детали курса (без авторизации)
  POST /courses           — создать курс (AdminUser)
  PUT  /courses/{id}      — обновить курс (AdminUser)
  DELETE /courses/{id}    — удалить курс (AdminUser) → 204 No Content

Коды ответов
────────────
  200 OK          — успешный GET / PUT
  201 Created     — успешный POST
  204 No Content  — успешный DELETE
  404 Not Found   — курс не найден
  409 Conflict    — конфликт данных (например, дублирование)
  422             — ошибка валидации Pydantic (автоматически FastAPI)
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AdminUser
from app.database import get_db
from app.models.course import Course
from app.schemas.course import (
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
)

logger = logging.getLogger(__name__)

# DbSession — локальный alias, чтобы не засорять сигнатуры
DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(
    prefix="/courses",
    tags=["Courses"],
)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ╚══════════════════════════════════════════════════════════════════════════════

async def _get_course_or_404(db: AsyncSession, course_id: int) -> Course:
    """
    Загружает курс по ID или бросает HTTP 404.

    Централизованная функция — не дублируем в каждом эндпоинте.

    Args:
        db:        Async-сессия SQLAlchemy.
        course_id: Первичный ключ курса.

    Returns:
        ORM-объект Course.

    Raises:
        HTTPException 404: курс с таким ID не найден.
    """
    course: Course | None = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Курс с id={course_id} не найден",
        )
    return course


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GET /courses — список опубликованных курсов
# ╚══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/",
    response_model=CourseListResponse,
    status_code=status.HTTP_200_OK,
    summary="Список опубликованных курсов",
    description=(
        "Возвращает постранично список всех опубликованных курсов. "
        "Доступен без авторизации — это публичный каталог платформы."
    ),
)
async def list_courses(
    db: DbSession,
    skip: int = Query(default=0, ge=0, description="Смещение (offset) для пагинации"),
    limit: int = Query(default=20, ge=1, le=100, description="Размер страницы (макс. 100)"),
) -> CourseListResponse:
    """
    Публичный каталог курсов с пагинацией offset/limit.

    Возвращает только опубликованные курсы (is_published=True).
    Вместе с items возвращает total — для построения UI-пагинации.
    """
    # Базовый фильтр — только опубликованные
    base_filter = Course.is_published.is_(True)

    # Общее количество для метаданных пагинации (отдельный COUNT-запрос)
    count_result = await db.execute(
        select(func.count()).select_from(Course).where(base_filter)
    )
    total: int = count_result.scalar_one()

    # Основная выборка с пагинацией и сортировкой по дате создания
    courses_result = await db.execute(
        select(Course)
        .where(base_filter)
        .order_by(Course.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    courses = list(courses_result.scalars().all())

    return CourseListResponse(
        items=[CourseResponse.model_validate(c) for c in courses],
        total=total,
        skip=skip,
        limit=limit,
    )


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GET /courses/{id} — детали курса
# ╚══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{course_id}",
    response_model=CourseResponse,
    status_code=status.HTTP_200_OK,
    summary="Детали курса",
    responses={
        404: {"description": "Курс не найден"},
    },
)
async def get_course(
    course_id: int,
    db: DbSession,
) -> CourseResponse:
    """
    Возвращает полные данные курса по ID.

    Доступен без авторизации.
    Возвращает курс независимо от статуса публикации —
    прямой доступ по ID используется и в admin-интерфейсе.
    """
    course = await _get_course_or_404(db, course_id)
    return CourseResponse.model_validate(course)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  POST /courses — создать курс
# ╚══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать курс",
    responses={
        201: {"description": "Курс успешно создан"},
        403: {"description": "Нет прав администратора"},
    },
)
async def create_course(
    payload: CourseCreate,
    db: DbSession,
    admin: AdminUser,       # проверяет авторизацию + is_admin
) -> CourseResponse:
    """
    Создаёт новый курс. Доступно только администраторам.

    Владельцем курса автоматически становится текущий admin-пользователь.
    Курс создаётся как черновик (is_published=False) если не указано иное.
    """
    new_course = Course(
        title=payload.title,
        description=payload.description,
        is_published=payload.is_published,
        owner_id=admin.id,   # автор курса = текущий администратор
    )
    db.add(new_course)

    try:
        await db.flush()       # INSERT в транзакцию, заполняет new_course.id
        await db.refresh(new_course)  # подтягивает server_default (created_at, updated_at)
    except IntegrityError as exc:
        await db.rollback()
        logger.error("Ошибка создания курса: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось создать курс: конфликт данных",
        ) from exc

    logger.info("Создан курс id=%d admin_id=%d", new_course.id, admin.id)
    return CourseResponse.model_validate(new_course)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  PUT /courses/{id} — обновить курс
# ╚══════════════════════════════════════════════════════════════════════════════

@router.put(
    "/{course_id}",
    response_model=CourseResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить курс",
    responses={
        404: {"description": "Курс не найден"},
        403: {"description": "Нет прав администратора"},
    },
)
async def update_course(
    course_id: int,
    payload: CourseUpdate,
    db: DbSession,
    _admin: AdminUser,      # только проверка прав, объект не нужен
) -> CourseResponse:
    """
    Обновляет поля курса. Доступно только администраторам.

    Обновляются только переданные поля (partial update через model_fields_set).
    Пустой запрос (все None) отклоняется Pydantic-валидатором в CourseUpdate.
    """
    course = await _get_course_or_404(db, course_id)

    # Обновляем только те поля, которые реально переданы в запросе
    # model_dump(exclude_unset=True) возвращает только явно указанные поля
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)

    # updated_at обновится автоматически через onupdate в TimestampMixin
    try:
        await db.flush()
        await db.refresh(course)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось обновить курс: конфликт данных",
        ) from exc

    logger.info("Обновлён курс id=%d поля=%s", course_id, list(update_data.keys()))
    return CourseResponse.model_validate(course)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  DELETE /courses/{id} — удалить курс
# ╚══════════════════════════════════════════════════════════════════════════════

@router.delete(
    "/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить курс",
    responses={
        204: {"description": "Курс удалён"},
        404: {"description": "Курс не найден"},
        403: {"description": "Нет прав администратора"},
    },
)
async def delete_course(
    course_id: int,
    db: DbSession,
    _admin: AdminUser,
) -> None:
    """
    Удаляет курс и все связанные уроки каскадно (cascade="all, delete-orphan").
    Доступно только администраторам.

    Возвращает 204 No Content — тело ответа пустое.
    """
    course = await _get_course_or_404(db, course_id)
    await db.delete(course)
    # Явный flush нужен, чтобы убедиться в успехе до commit в get_db
    await db.flush()

    logger.info("Удалён курс id=%d", course_id)
    # FastAPI автоматически вернёт 204 при return None с status_code=204
