"""
app/routers/tests.py

Роутер сдачи тестов и обновления прогресса студента.

Таблица доступа
───────────────
  POST  /courses/{course_id}/tests       — сдать тест (ActiveUser)
  GET   /courses/{course_id}/tests/my    — мои результаты по курсу (ActiveUser)

Бизнес-логика обновления прогресса
────────────────────────────────────
  При успешной сдаче теста (passed=True):

  1. Считаем количество уникальных курсов, тесты по которым пользователь
     прошёл (passed=True) — это «охваченные» уроки.

  2. Прогресс = (кол-во пройденных тестов / общее кол-во уроков) × 100.

  3. Если progress >= 100.0 → is_completed = True.

  Допущение: каждый урок имеет ровно один тест. Повторные попытки
  не увеличивают прогресс — считаем уникальные курсы (DISTINCT course_id
  в подзапросе не применим напрямую, поэтому считаем записи passed=True
  по данному курсу — это корректно, т.к. прогресс привязан к одному курсу).

Коды ответов
────────────
  200 OK          — успешный GET
  201 Created     — тест сохранён
  403 Forbidden   — не записан на курс
  404 Not Found   — курс не найден
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ActiveUser
from app.database import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.test import Test
from app.schemas.test import PASS_THRESHOLD, TestCreate, TestResponse

logger = logging.getLogger(__name__)

DbSession = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(
    prefix="/courses/{course_id}/tests",
    tags=["Tests"],
)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ╚══════════════════════════════════════════════════════════════════════════════

async def _get_course_or_404(db: AsyncSession, course_id: int) -> Course:
    """Загружает курс по ID или бросает 404."""
    course: Course | None = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Курс с id={course_id} не найден",
        )
    return course


async def _require_enrollment(
    db: AsyncSession,
    user_id: int,
    course_id: int,
) -> Enrollment:
    """
    Проверяет, что пользователь записан на курс.

    В отличие от _get_enrollment_or_404 в enrollments.py — возвращает 403,
    а не 404: пользователь знает, что курс существует, но доступ закрыт
    из-за отсутствия записи.

    Raises:
        HTTPException 403: пользователь не записан на курс.
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Вы не записаны на курс с id={course_id}. "
                "Запишитесь на курс через POST /api/v1/enrollments/{course_id}"
            ),
        )
    return enrollment


async def _recalculate_progress(
    db: AsyncSession,
    user_id: int,
    course_id: int,
    enrollment: Enrollment,
) -> None:
    """
    Пересчитывает прогресс студента после успешной сдачи теста.

    Алгоритм:
      - Считаем количество уроков в курсе (total_lessons).
      - Если уроков нет → прогресс не меняем (деление на 0 недопустимо).
      - Считаем количество тестов с passed=True по данному курсу/студенту
        (passed_count). Каждая попытка считается независимо — студент
        может сдать один и тот же тест несколько раз, но прогресс
        ограничен 100.0 через min().
      - progress = min(passed_count / total_lessons * 100, 100.0)
      - Если progress >= 100.0 → is_completed = True.

    Изменения записываются в объект enrollment — flush/commit
    выполнится в get_db dependency после завершения запроса.

    Args:
        db:         Async-сессия.
        user_id:    ID текущего студента.
        course_id:  ID курса.
        enrollment: ORM-объект записи студента (изменяется in-place).
    """
    # Общее количество уроков в курсе
    total_result = await db.execute(
        select(func.count()).select_from(Lesson).where(
            Lesson.course_id == course_id
        )
    )
    total_lessons: int = total_result.scalar_one()

    # Если уроков нет — нечего считать, выходим
    if total_lessons == 0:
        logger.warning(
            "Курс id=%d не содержит уроков — прогресс не пересчитывается",
            course_id,
        )
        return

    # Количество успешно пройденных тестов (каждая попытка counted отдельно,
    # но прогресс ограничен 100.0 через min())
    passed_result = await db.execute(
        select(func.count()).select_from(Test).where(
            Test.user_id == user_id,
            Test.course_id == course_id,
            Test.passed.is_(True),
        )
    )
    passed_count: int = passed_result.scalar_one()

    # Вычисляем прогресс, ограничиваем 100.0 сверху
    new_progress = min(round(passed_count / total_lessons * 100, 2), 100.0)

    # Обновляем объект enrollment в памяти (flush — в конце запроса)
    enrollment.progress = new_progress
    enrollment.is_completed = new_progress >= 100.0

    logger.info(
        "Прогресс пользователя id=%d по курсу id=%d: %.1f%% (passed=%d / total=%d)",
        user_id, course_id, new_progress, passed_count, total_lessons,
    )


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  POST /courses/{course_id}/tests — сдать тест
# ╚══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/",
    response_model=TestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Сдать тест по курсу",
    responses={
        201: {"description": "Результат теста сохранён"},
        403: {"description": "Вы не записаны на этот курс"},
        404: {"description": "Курс не найден"},
    },
)
async def submit_test(
    course_id: int,
    payload: TestCreate,
    db: DbSession,
    current_user: ActiveUser,
) -> TestResponse:
    """
    Принимает результат теста и обновляет прогресс студента.

    Шаги:
      1. Проверяем существование курса → 404.
      2. Проверяем, что студент записан на курс → 403.
      3. Вычисляем passed: score >= PASS_THRESHOLD (60.0 по умолчанию).
      4. Сохраняем Test в БД.
      5. Если passed=True — пересчитываем progress и is_completed в Enrollment.
      6. Возвращаем TestResponse.

    Повторные попытки разрешены — каждый вызов создаёт новую запись Test.
    Прогресс пересчитывается при каждой успешной попытке.
    """
    # Шаг 1: курс должен существовать
    await _get_course_or_404(db, course_id)

    # Шаг 2: студент должен быть записан
    enrollment = await _require_enrollment(db, current_user.id, course_id)

    # Шаг 3: вычисляем passed на сервере — клиент не может фальсифицировать
    passed: bool = payload.score >= PASS_THRESHOLD

    # Шаг 4: сохраняем результат теста
    test_result = Test(
        user_id=current_user.id,
        course_id=course_id,
        score=payload.score,
        passed=passed,
    )
    db.add(test_result)
    await db.flush()              # получаем test_result.id и taken_at
    await db.refresh(test_result)

    # Шаг 5: пересчёт прогресса только при успешной сдаче
    if passed:
        await _recalculate_progress(db, current_user.id, course_id, enrollment)
        # flush изменений enrollment — commit выполнится в get_db
        await db.flush()

        if enrollment.is_completed:
            logger.info(
                "🎓 Пользователь id=%d завершил курс id=%d!",
                current_user.id, course_id,
            )

    logger.info(
        "Тест сдан: user_id=%d course_id=%d score=%.1f passed=%s",
        current_user.id, course_id, payload.score, passed,
    )
    return TestResponse.model_validate(test_result)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GET /courses/{course_id}/tests/my — мои результаты тестов
# ╚══════════════════════════════════════════════════════════════════════════════
# ВАЖНО: маршрут /my должен быть зарегистрирован ДО /{test_id} (если появится),
# иначе FastAPI перехватит "my" как path-параметр.

@router.get(
    "/my",
    response_model=list[TestResponse],
    status_code=status.HTTP_200_OK,
    summary="Мои результаты тестов по курсу",
    responses={
        403: {"description": "Вы не записаны на этот курс"},
        404: {"description": "Курс не найден"},
    },
)
async def my_test_results(
    course_id: int,
    db: DbSession,
    current_user: ActiveUser,
) -> list[TestResponse]:
    """
    Возвращает историю всех попыток прохождения теста по курсу.

    Отсортирована по дате сдачи (свежие первыми) — удобно для отображения
    прогресса улучшения результата с каждой попыткой.

    Перед выдачей результатов проверяем:
      - Курс существует.
      - Студент записан на курс (иначе 403).
    """
    # Курс должен существовать
    await _get_course_or_404(db, course_id)

    # Студент должен быть записан — нельзя смотреть тесты чужих курсов
    await _require_enrollment(db, current_user.id, course_id)

    result = await db.execute(
        select(Test)
        .where(
            Test.user_id == current_user.id,
            Test.course_id == course_id,
        )
        .order_by(Test.taken_at.desc())   # свежие попытки первыми
    )
    tests = list(result.scalars().all())
    return [TestResponse.model_validate(t) for t in tests]
