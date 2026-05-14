"""
app/routers/analytics.py

Роутер аналитики для платформы онлайн-обучения.
Предоставляет эндпоинты общей статистики (для админов) и
личной статистики студента.
"""

from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ActiveUser, AdminUser
from app.database import DbSession
from app.models.certificate import Certificate
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.test import Test
from app.models.user import User
from app.database import DbSession

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ---------------------------------------------------------------------------
# Pydantic v2 схемы ответов
# ---------------------------------------------------------------------------


class PlatformStatsResponse(BaseModel):
    """Общая статистика платформы."""

    total_users: int
    total_courses: int
    total_enrollments: int
    total_certificates: int
    total_lessons: int


class TopCourseItem(BaseModel):
    """Один элемент в списке топ-курсов."""

    course_id: int
    title: str
    enrollment_count: int


class TopCoursesResponse(BaseModel):
    """Топ-5 курсов по количеству записей."""

    courses: list[TopCourseItem]


class MyStatsResponse(BaseModel):
    """Личная статистика студента."""

    enrolled_courses: int
    completed_courses: int
    certificates_count: int
    average_score: float | None  # None, если студент ещё не сдавал тестов
    total_tests_taken: int


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=PlatformStatsResponse,
    summary="Общая статистика платформы",
    description="Доступно только администраторам.",
)
async def get_platform_stats(
    db: DbSession,
    _admin: AdminUser,  # проверка прав; тело не используется
) -> PlatformStatsResponse:
    """
    Возвращает агрегированные счётчики по всей платформе.
    Все запросы выполняются одним round-trip к БД через scalar().
    """

    # Считаем каждую сущность отдельным scalars-запросом.
    # При желании можно объединить в один SELECT с несколькими func.count(),
    # но раздельные запросы читаются проще и проще тестируются.

    total_users: int = await db.scalar(select(func.count()).select_from(User)) or 0
    total_courses: int = await db.scalar(select(func.count()).select_from(Course)) or 0
    total_enrollments: int = (
        await db.scalar(select(func.count()).select_from(Enrollment)) or 0
    )
    total_certificates: int = (
        await db.scalar(select(func.count()).select_from(Certificate)) or 0
    )
    total_lessons: int = await db.scalar(select(func.count()).select_from(Lesson)) or 0

    return PlatformStatsResponse(
        total_users=total_users,
        total_courses=total_courses,
        total_enrollments=total_enrollments,
        total_certificates=total_certificates,
        total_lessons=total_lessons,
    )


@router.get(
    "/top-courses",
    response_model=TopCoursesResponse,
    summary="Топ-5 курсов по записям",
    description="Доступно только администраторам.",
)
async def get_top_courses(
    db: DbSession,
    _admin: AdminUser,
) -> TopCoursesResponse:
    """
    Возвращает 5 курсов с наибольшим количеством записей (Enrollment).

    Используется LEFT OUTER JOIN, чтобы курсы без записей тоже попадали
    в выборку (с enrollment_count = 0) — это полезно на старте платформы.
    """

    # enrollment_count — псевдоним агрегатной колонки
    enrollment_count_col = func.count(Enrollment.id).label("enrollment_count")

    stmt = (
        select(
            Course.id.label("course_id"),
            Course.title,
            enrollment_count_col,
        )
        .outerjoin(Enrollment, Enrollment.course_id == Course.id)
        .group_by(Course.id, Course.title)
        .order_by(enrollment_count_col.desc())
        .limit(5)
    )

    rows = (await db.execute(stmt)).all()

    courses = [
        TopCourseItem(
            course_id=row.course_id,
            title=row.title,
            enrollment_count=row.enrollment_count,
        )
        for row in rows
    ]

    return TopCoursesResponse(courses=courses)


@router.get(
    "/my-stats",
    response_model=MyStatsResponse,
    summary="Личная статистика студента",
    description="Доступно любому авторизованному пользователю.",
)
async def get_my_stats(
    db: DbSession,
    current_user: ActiveUser,
) -> MyStatsResponse:
    """
    Возвращает персональную статистику текущего пользователя:
    - сколько курсов он записался / завершил,
    - количество сертификатов,
    - средний балл и число сданных тестов.

    Предполагается, что:
    - Enrollment.is_completed: bool — признак завершения курса.
    - Test.score: float | None — балл за тест (None = ещё не сдан / нет попытки).
      Если в вашей схеме используется другое поле, скорректируйте запрос ниже.
    """

    user_id: int = current_user.id

    # --- Количество записей на курсы ---
    enrolled_courses: int = (
        await db.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(Enrollment.user_id == user_id)
        )
        or 0
    )

    # --- Количество завершённых курсов ---
    completed_courses: int = (
        await db.scalar(
            select(func.count())
            .select_from(Enrollment)
            .where(
                Enrollment.user_id == user_id,
                Enrollment.is_completed.is_(True),
            )
        )
        or 0
    )

    # --- Количество сертификатов ---
    certificates_count: int = (
        await db.scalar(
            select(func.count())
            .select_from(Certificate)
            .where(Certificate.user_id == user_id)
        )
        or 0
    )

    # --- Тесты: средний балл и общее количество сданных ---
    # func.avg вернёт None, если нет строк с ненулевым score
    tests_stmt = select(
        func.avg(Test.score).label("avg_score"),
        func.count(Test.id).label("tests_taken"),
    ).where(
        Test.user_id == user_id,
        Test.score.is_not(None),  # учитываем только завершённые попытки
    )

    tests_row = (await db.execute(tests_stmt)).one()

    average_score: float | None = (
        float(tests_row.avg_score) if tests_row.avg_score is not None else None
    )
    total_tests_taken: int = tests_row.tests_taken or 0

    return MyStatsResponse(
        enrolled_courses=enrolled_courses,
        completed_courses=completed_courses,
        certificates_count=certificates_count,
        average_score=average_score,
        total_tests_taken=total_tests_taken,
    )
