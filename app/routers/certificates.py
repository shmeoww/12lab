"""
app/routers/certificates.py

Роутер выдачи и верификации сертификатов об окончании курсов.

Таблица доступа
───────────────
  POST  /certificates/{course_id}           — выдать сертификат (ActiveUser)
  GET   /certificates/my                    — мои сертификаты (ActiveUser)
  GET   /certificates/{certificate_number}  — верифицировать (публичный)

Порядок маршрутов
─────────────────
  GET /certificates/my ОБЯЗАН стоять до GET /certificates/{certificate_number}.
  Иначе FastAPI попытается использовать строку "my" как certificate_number
  и вернёт 404 вместо списка сертификатов.

Формат certificate_number
──────────────────────────
  CERT-{YEAR}-{UUID4[:8].upper()}
  Пример: CERT-2024-A1B2C3D4

  - YEAR  — год выдачи (4 цифры), полезен при визуальной проверке
  - UUID4 — первые 8 символов UUID4 в верхнем регистре (32^8 ≈ 1 трлн вариантов)

  Общая вероятность коллизии пренебрежимо мала, но при IntegrityError
  роутер делает повторную попытку с новым UUID (до 3 раз).

Коды ответов
────────────
  200 OK         — успешный GET
  201 Created    — сертификат выдан
  400 Bad Request— курс не завершён
  404 Not Found  — курс/сертификат не найден
  409 Conflict   — сертификат уже был выдан ранее
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ActiveUser
from app.database import get_db
from app.models.certificate import Certificate
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.schemas.certificate import CertificateResponse, CertificateVerifyResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Максимальное число попыток при коллизии certificate_number (крайне маловероятно)
_MAX_CERT_NUMBER_RETRIES: int = 3

router = APIRouter(
    prefix="/certificates",
    tags=["Certificates"],
)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  УТИЛИТЫ
# ╚══════════════════════════════════════════════════════════════════════════════

def _make_certificate_number(year: int | None = None) -> str:
    """
    Генерирует уникальный номер сертификата.

    Формат: CERT-{YEAR}-{UUID4[:8].upper()}
    Пример: CERT-2024-A1B2C3D4

    Args:
        year: Год выдачи. None → текущий год по UTC.

    Returns:
        Строка номера сертификата (не более 20 символов,
        вписывается в поле String(50) модели Certificate).
    """
    if year is None:
        year = datetime.now(timezone.utc).year
    suffix = uuid.uuid4().hex[:8].upper()   # 8 hex-символов UUID4 → верхний регистр
    return f"CERT-{year}-{suffix}"


async def _get_enrollment_with_progress(
    db: AsyncSession,
    user_id: int,
    course_id: int,
) -> Enrollment:
    """
    Загружает запись студента на курс.

    Используется для проверки факта записи и уровня прогресса
    перед выдачей сертификата.

    Raises:
        HTTPException 404: запись не найдена (студент не записан на курс).
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


async def _get_existing_certificate(
    db: AsyncSession,
    user_id: int,
    course_id: int,
) -> Certificate | None:
    """
    Ищет уже выданный сертификат по паре (user_id, course_id).

    Returns:
        ORM-объект Certificate или None если сертификат ещё не выдавался.
    """
    result = await db.execute(
        select(Certificate).where(
            Certificate.user_id == user_id,
            Certificate.course_id == course_id,
        )
    )
    return result.scalar_one_or_none()


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  POST /certificates/{course_id} — выдать сертификат
# ╚══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/{course_id}",
    response_model=CertificateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Получить сертификат о прохождении курса",
    responses={
        201: {"description": "Сертификат успешно выдан"},
        400: {"description": "Курс ещё не завершён — указан текущий прогресс"},
        404: {"description": "Курс не найден или вы не записаны на него"},
        409: {"description": "Сертификат по этому курсу уже был выдан ранее"},
    },
)
async def issue_certificate(
    course_id: int,
    db: DbSession,
    current_user: ActiveUser,
) -> CertificateResponse:
    """
    Выдаёт сертификат студенту, завершившему курс.

    Шаги:
      1. Проверяем существование курса → 404.
      2. Загружаем Enrollment → 404 если не записан.
      3. Проверяем is_completed=True → 400 с текущим прогрессом если нет.
      4. Проверяем, что сертификат ещё не выдавался → 409 если уже есть.
      5. Генерируем уникальный certificate_number (до 3 попыток при коллизии).
      6. Сохраняем Certificate в БД.
      7. Возвращаем CertificateResponse.

    Идемпотентность: если вызвать повторно — вернётся 409 со ссылкой
    на уже существующий сертификат. Клиент может получить его через
    GET /certificates/my.
    """
    # ── Шаг 1: курс должен существовать ──────────────────────────────────────
    course: Course | None = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Курс с id={course_id} не найден",
        )

    # ── Шаг 2: студент должен быть записан на курс ────────────────────────────
    enrollment = await _get_enrollment_with_progress(db, current_user.id, course_id)

    # ── Шаг 3: курс должен быть полностью завершён ───────────────────────────
    if not enrollment.is_completed:
        # Возвращаем текущий прогресс в сообщении — полезно для клиента
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Курс ещё не завершён. "
                f"Ваш текущий прогресс: {enrollment.progress:.1f}%. "
                "Для получения сертификата необходимо набрать 100%"
            ),
        )

    # ── Шаг 4: сертификат не должен быть выдан ранее ─────────────────────────
    existing = await _get_existing_certificate(db, current_user.id, course_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Сертификат по этому курсу уже был выдан. "
                f"Номер: {existing.certificate_number}. "
                "Получить его можно через GET /api/v1/certificates/my"
            ),
        )

    # ── Шаг 5 & 6: генерация номера и сохранение ─────────────────────────────
    # Делаем до _MAX_CERT_NUMBER_RETRIES попыток на случай крайне редкой коллизии
    # (коллизия UUID4[:8] — вероятность ~1 к 4 млрд, но обрабатываем корректно)
    year = datetime.now(timezone.utc).year
    last_exc: Exception | None = None

    for attempt in range(1, _MAX_CERT_NUMBER_RETRIES + 1):
        cert_number = _make_certificate_number(year)
        certificate = Certificate(
            user_id=current_user.id,
            course_id=course_id,
            certificate_number=cert_number,
        )
        db.add(certificate)

        try:
            await db.flush()          # INSERT → получаем id, issued_at
            await db.refresh(certificate)
            break                     # успех — выходим из цикла
        except IntegrityError as exc:
            await db.rollback()
            last_exc = exc
            logger.warning(
                "Коллизия certificate_number=%s (попытка %d/%d)",
                cert_number, attempt, _MAX_CERT_NUMBER_RETRIES,
            )
            # На следующей итерации сгенерируем новый номер
    else:
        # pragma: no cover
        logger.error(
            "Не удалось сгенерировать уникальный номер сертификата "
            "после %d попыток: %s",
            _MAX_CERT_NUMBER_RETRIES, last_exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать сертификат. Попробуйте позже",
        )

    logger.info(
        "🎓 Выдан сертификат %s: user_id=%d course_id=%d",
        certificate.certificate_number, current_user.id, course_id,
    )
    return CertificateResponse.model_validate(certificate)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GET /certificates/my — мои сертификаты
# ╚══════════════════════════════════════════════════════════════════════════════
# ВАЖНО: этот маршрут должен стоять ДО GET /{certificate_number},
# иначе строка "my" будет перехвачена как path-параметр certificate_number.

@router.get(
    "/my",
    response_model=list[CertificateResponse],
    status_code=status.HTTP_200_OK,
    summary="Мои сертификаты",
    description="Возвращает все сертификаты текущего пользователя, от свежих к старым.",
)
async def my_certificates(
    db: DbSession,
    current_user: ActiveUser,
) -> list[CertificateResponse]:
    """
    Возвращает список всех сертификатов текущего пользователя.

    Сортировка по дате выдачи — свежие первыми.
    Пустой список допустим: студент ещё не завершил ни одного курса.
    """
    result = await db.execute(
        select(Certificate)
        .where(Certificate.user_id == current_user.id)
        .order_by(Certificate.issued_at.desc())
    )
    certs = list(result.scalars().all())
    return [CertificateResponse.model_validate(c) for c in certs]


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GET /certificates/{certificate_number} — верификация (публичный)
# ╚══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{certificate_number}",
    response_model=CertificateVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Верифицировать сертификат",
    description=(
        "Публичный эндпоинт — авторизация не требуется. "
        "Позволяет работодателям и третьим лицам проверить подлинность сертификата "
        "по его уникальному номеру."
    ),
    responses={
        200: {"description": "Сертификат найден и действителен"},
        404: {"description": "Сертификат с таким номером не существует"},
    },
)
async def verify_certificate(
    certificate_number: str,
    db: DbSession,
) -> CertificateVerifyResponse:
    """
    Верифицирует сертификат по уникальному номеру.

    Публичный эндпоинт — авторизация НЕ требуется.
    Возвращает расширенную информацию: имя студента и название курса,
    чтобы верифицирующая сторона не делала дополнительных запросов.

    Args:
        certificate_number: Номер сертификата из URL (например, CERT-2024-A1B2C3D4).

    Returns:
        CertificateVerifyResponse с полной информацией о сертификате.

    Raises:
        HTTPException 404: сертификат с таким номером не найден в БД.
    """
    # Ищем сертификат по номеру — загружаем вместе со связанными объектами
    # (user и course подгрузятся через lazy="joined" из модели Certificate)
    result = await db.execute(
        select(Certificate)
        .options(
            selectinload(Certificate.user),
            selectinload(Certificate.course),
        )
        .where(Certificate.certificate_number == certificate_number)
    )
    certificate: Certificate | None = result.scalar_one_or_none()

    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сертификат с номером '{certificate_number}' не найден. "
                   "Убедитесь, что номер введён корректно",
        )

    # Имя студента: full_name если задано, иначе email — публичная страница
    # не должна показывать email без явного согласия, но это упрощённый вариант.
    # В продакшне — отдельный флаг "публичный профиль".
    student_name: str = certificate.user.full_name or certificate.user.email

    logger.info("Верификация сертификата %s", certificate_number)

    return CertificateVerifyResponse(
        certificate_number=certificate.certificate_number,
        issued_at=certificate.issued_at,
        course_id=certificate.course_id,
        course_title=certificate.course.title,
        user_id=certificate.user_id,
        student_name=student_name,
        is_valid=True,
    )
