"""
app/routers/lessons.py

CRUD-роутер для уроков, вложенных в курсы.

Таблица доступа
───────────────
  GET  /courses/{course_id}/lessons          — список уроков курса (ActiveUser)
  GET  /courses/{course_id}/lessons/{id}     — детали урока (ActiveUser)
  POST /courses/{course_id}/lessons          — создать урок (AdminUser)
  PUT  /courses/{course_id}/lessons/{id}     — обновить урок (AdminUser)
  DELETE /courses/{course_id}/lessons/{id}   — удалить урок (AdminUser) → 204

Вложенная маршрутизация
────────────────────────
  Роутер регистрируется в main.py с prefix="/api/v1":
      app.include_router(lessons.router, prefix="/api/v1")

  Сам роутер имеет prefix="/courses/{course_id}/lessons",
  что даёт итоговый путь: /api/v1/courses/{course_id}/lessons/...

Инварианты
──────────
  - Все операции сначала проверяют существование родительского курса.
  - Урок принадлежит курсу — запрос к несуществующему курсу всегда даёт 404,
    даже если урок с таким id существует в другом курсе.
  - При конфликте order (UniqueConstraint) возвращается 409.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ActiveUser, AdminUser
from app.database import get_db
from app.models.course import Course
from app.models.lesson import Lesson
from app.schemas.lesson import LessonCreate, LessonResponse, LessonUpdate

logger = logging.getLogger(__name__)

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(
    # course_id — path-параметр, пробрасывается во все эндпоинты автоматически
    prefix="/courses/{course_id}/lessons",
    tags=["Lessons"],
)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ╚══════════════════════════════════════════════════════════════════════════════

async def _get_course_or_404(db: AsyncSession, course_id: int) -> Course:
    """
    Проверяет существование родительского курса.

    Вызывается в каждом эндпоинте уроков — гарантирует, что клиент
    не может работать с уроками несуществующего курса.

    Raises:
        HTTPException 404: курс не найден.
    """
    course: Course | None = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Курс с id={course_id} не найден",
        )
    return course


async def _get_lesson_or_404(
    db: AsyncSession,
    course_id: int,
    lesson_id: int,
) -> Lesson:
    """
    Загружает урок по ID с проверкой принадлежности к курсу.

    Два условия WHERE: lesson.id И lesson.course_id.
    Это гарантирует, что урок принадлежит именно этому курсу,
    а не другому — иначе возможна утечка данных через перебор ID.

    Args:
        db:        Async-сессия.
        course_id: ID курса из URL.
        lesson_id: ID урока из URL.

    Returns:
        ORM-объект Lesson.

    Raises:
        HTTPException 404: урок не найден или не принадлежит курсу.
    """
    result = await db.execute(
        select(Lesson).where(
            Lesson.id == lesson_id,
            Lesson.course_id == course_id,  # проверка принадлежности к курсу
        )
    )
    lesson: Lesson | None = result.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Урок с id={lesson_id} не найден в курсе id={course_id}",
        )
    return lesson


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GET /courses/{course_id}/lessons — список уроков
# ╚══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/",
    response_model=list[LessonResponse],
    status_code=status.HTTP_200_OK,
    summary="Список уроков курса",
    responses={
        404: {"description": "Курс не найден"},
    },
)
async def list_lessons(
    course_id: int,
    db: DbSession,
    _user: ActiveUser,      # требует авторизации; сам объект не нужен
) -> list[LessonResponse]:
    """
    Возвращает все уроки курса, отсортированные по полю order.

    Доступно любому авторизованному пользователю (студенты и админы).
    Сначала проверяем существование курса — без этого непонятно,
    пустой ли список или курс вообще не существует.
    """
    await _get_course_or_404(db, course_id)

    result = await db.execute(
        select(Lesson)
        .where(Lesson.course_id == course_id)
        .order_by(Lesson.order)     # уроки всегда в правильном порядке
    )
    lessons = list(result.scalars().all())
    return [LessonResponse.model_validate(lesson) for lesson in lessons]


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GET /courses/{course_id}/lessons/{id} — детали урока
# ╚══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{lesson_id}",
    response_model=LessonResponse,
    status_code=status.HTTP_200_OK,
    summary="Детали урока",
    responses={
        404: {"description": "Курс или урок не найден"},
    },
)
async def get_lesson(
    course_id: int,
    lesson_id: int,
    db: DbSession,
    _user: ActiveUser,
) -> LessonResponse:
    """
    Возвращает полные данные урока по ID.

    Проверяет принадлежность урока к указанному курсу —
    нельзя получить урок из чужого курса, угадав его ID.
    """
    # Сначала убеждаемся, что курс существует — иначе ошибка неоднозначна
    await _get_course_or_404(db, course_id)
    lesson = await _get_lesson_or_404(db, course_id, lesson_id)
    return LessonResponse.model_validate(lesson)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  POST /courses/{course_id}/lessons — создать урок
# ╚══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/",
    response_model=LessonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать урок",
    responses={
        201: {"description": "Урок успешно создан"},
        404: {"description": "Курс не найден"},
        409: {"description": "Урок с таким порядковым номером уже существует"},
        403: {"description": "Нет прав администратора"},
    },
)
async def create_lesson(
    course_id: int,
    payload: LessonCreate,
    db: DbSession,
    _admin: AdminUser,
) -> LessonResponse:
    """
    Создаёт новый урок в курсе. Доступно только администраторам.

    Поле order должно быть уникальным внутри курса.
    При конфликте (UniqueConstraint в БД) возвращается 409.
    """
    # Убеждаемся, что курс существует перед созданием урока
    await _get_course_or_404(db, course_id)

    new_lesson = Lesson(
        title=payload.title,
        content=payload.content,
        order=payload.order,
        course_id=course_id,
    )
    db.add(new_lesson)

    try:
        await db.flush()
        await db.refresh(new_lesson)
    except IntegrityError as exc:
        await db.rollback()
        # UniqueConstraint "uq_lesson_course_order" сработал
        logger.warning(
            "Конфликт order=%d при создании урока в курсе id=%d",
            payload.order, course_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"В курсе id={course_id} уже существует урок "
                f"с порядковым номером {payload.order}. "
                "Используйте другое значение поля 'order'"
            ),
        ) from exc

    logger.info(
        "Создан урок id=%d order=%d в курсе id=%d",
        new_lesson.id, new_lesson.order, course_id,
    )
    return LessonResponse.model_validate(new_lesson)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  PUT /courses/{course_id}/lessons/{id} — обновить урок
# ╚══════════════════════════════════════════════════════════════════════════════

@router.put(
    "/{lesson_id}",
    response_model=LessonResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить урок",
    responses={
        404: {"description": "Курс или урок не найден"},
        409: {"description": "Конфликт порядкового номера"},
        403: {"description": "Нет прав администратора"},
    },
)
async def update_lesson(
    course_id: int,
    lesson_id: int,
    payload: LessonUpdate,
    db: DbSession,
    _admin: AdminUser,
) -> LessonResponse:
    """
    Обновляет поля урока. Доступно только администраторам.

    Обновляются только переданные поля (exclude_unset=True).
    При изменении order проверяется уникальность в рамках курса.
    """
    await _get_course_or_404(db, course_id)
    lesson = await _get_lesson_or_404(db, course_id, lesson_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lesson, field, value)

    try:
        await db.flush()
        await db.refresh(lesson)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"В курсе id={course_id} конфликт порядкового номера урока",
        ) from exc

    logger.info(
        "Обновлён урок id=%d в курсе id=%d поля=%s",
        lesson_id, course_id, list(update_data.keys()),
    )
    return LessonResponse.model_validate(lesson)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  DELETE /courses/{course_id}/lessons/{id} — удалить урок
# ╚══════════════════════════════════════════════════════════════════════════════

@router.delete(
    "/{lesson_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить урок",
    responses={
        204: {"description": "Урок удалён"},
        404: {"description": "Курс или урок не найден"},
        403: {"description": "Нет прав администратора"},
    },
)
async def delete_lesson(
    course_id: int,
    lesson_id: int,
    db: DbSession,
    _admin: AdminUser,
) -> None:
    """
    Удаляет урок из курса. Доступно только администраторам.

    После удаления рекомендуется перенумеровать оставшиеся уроки
    (это ответственность клиента или отдельного эндпоинта).
    Возвращает 204 No Content.
    """
    await _get_course_or_404(db, course_id)
    lesson = await _get_lesson_or_404(db, course_id, lesson_id)

    await db.delete(lesson)
    await db.flush()

    logger.info("Удалён урок id=%d из курса id=%d", lesson_id, course_id)
