"""
app/routers/auth.py

Роутер аутентификации — регистрация, вход, обновление токена.

Эндпоинты
─────────
  POST /auth/register  — регистрация нового пользователя
  POST /auth/login     — вход: возвращает пару JWT-токенов
  POST /auth/refresh   — обновление access-токена по refresh-токену

Коды ответов
────────────
  201 Created           — успешная регистрация
  200 OK                — успешный вход / обновление токена
  409 Conflict          — email уже зарегистрирован
  401 Unauthorized      — неверный email/пароль или недействительный токен
  403 Forbidden         — аккаунт заблокирован (is_active=False)
  422 Unprocessable     — ошибка валидации Pydantic (автоматически FastAPI)
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_token_pair,
    decode_refresh_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)

# ── Аннотация зависимости сессии БД (сокращает сигнатуры функций) ─────────────
DbSession = Annotated[AsyncSession, Depends(get_db)]

# Фиктивный хэш для защиты от user enumeration attack.
# Используется в /login когда пользователь не найден —
# чтобы время ответа было одинаковым независимо от результата поиска.
_DUMMY_HASH: str = "$2b$12$KIXjJ9i5QnGD8Z6nZJFKwuFCKVF3KX5QnGD8Z6nZJFKwuDummyHash"


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (не являются эндпоинтами)
# ╚══════════════════════════════════════════════════════════════════════════════

async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Находит пользователя по email.

    Выделена в отдельную функцию, т.к. используется в нескольких эндпоинтах.
    Возвращает None (не бросает исключение) — решение об ответе принимает вызывающий код.

    Args:
        db:    Сессия SQLAlchemy.
        email: E-mail для поиска (ожидается нормализованный нижний регистр).

    Returns:
        ORM-объект User или None, если пользователь не найден.
    """
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def _issue_tokens_for_user(user: User) -> TokenResponse:
    """
    Выпускает пару токенов для пользователя и формирует TokenResponse.

    Вынесено в отдельную функцию, т.к. используется и в /login, и в /refresh.

    Args:
        user: Аутентифицированный ORM-объект User.

    Returns:
        TokenResponse с access_token, refresh_token и token_type="bearer".
    """
    access_token, refresh_token = create_token_pair(email=user.email)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  POST /auth/register
# ╚══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
    responses={
        201: {"description": "Пользователь успешно зарегистрирован"},
        409: {"description": "Пользователь с таким email уже существует"},
        422: {"description": "Ошибка валидации входных данных"},
    },
)
async def register(
    payload: UserCreate,
    db: DbSession,
) -> UserResponse:
    """
    Регистрирует нового пользователя на платформе.

    Шаги:
      1. Проверяем, не занят ли email → 409 если занят.
      2. Хэшируем пароль через bcrypt.
      3. Сохраняем нового User в БД.
      4. Возвращаем UserResponse (без пароля).

    Пароль НИКОГДА не попадает в лог и не возвращается в ответе.
    """
    # ── Шаг 1: проверка уникальности email ───────────────────────────────────
    existing_user = await _get_user_by_email(db, payload.email)
    if existing_user is not None:
        # Не раскрываем детали — просто сообщаем, что email занят.
        # Логируем без email, чтобы не засорять логи PII.
        logger.info("Попытка регистрации на уже занятый email (id=%d)", existing_user.id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже зарегистрирован",
        )

    # ── Шаг 2: хэширование пароля ─────────────────────────────────────────────
    # hash_password() генерирует уникальную соль для каждого вызова
    hashed = hash_password(payload.password)

    # ── Шаг 3: создание и сохранение пользователя ────────────────────────────
    new_user = User(
        email=payload.email,          # уже нормализован в UserCreate
        hashed_password=hashed,
        full_name=payload.full_name,
        # is_admin и is_active берут значения по умолчанию из модели
    )
    db.add(new_user)

    # flush записывает INSERT в транзакцию и заполняет new_user.id,
    # но не делает commit — он выполнится в get_db dependency после yield.
    await db.flush()
    # refresh подтягивает server_default-поля (created_at) из БД
    await db.refresh(new_user)

    logger.info("Зарегистрирован новый пользователь id=%d", new_user.id)

    # ── Шаг 4: возврат ответа ─────────────────────────────────────────────────
    # model_validate читает атрибуты ORM-объекта благодаря from_attributes=True
    return UserResponse.model_validate(new_user)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  POST /auth/login
# ╚══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Вход в аккаунт",
    responses={
        200: {"description": "Успешный вход, пара JWT-токенов выдана"},
        401: {"description": "Неверный email или пароль"},
        403: {"description": "Аккаунт заблокирован администратором"},
    },
)
async def login(
    payload: UserLogin,
    db: DbSession,
) -> TokenResponse:
    """
    Аутентифицирует пользователя и выдаёт пару JWT-токенов.

    Шаги:
      1. Ищем пользователя по email.
      2. Проверяем пароль через bcrypt.
      3. Проверяем is_active.
      4. При необходимости обновляем хэш пароля (needs_rehash).
      5. Возвращаем TokenResponse.

    Безопасность:
      - Ошибки «email не найден» и «пароль неверен» возвращают ОДИНАКОВЫЙ
        HTTP 401 с одинаковым текстом — это защита от user enumeration attack.
      - verify_password использует timing-safe сравнение (constant time).
    """
    # ── Шаг 1: поиск пользователя ─────────────────────────────────────────────
    user = await _get_user_by_email(db, payload.email)

    # ── Шаг 2: проверка пароля ────────────────────────────────────────────────
    # ВАЖНО: verify_password вызываем ВСЕГДА, даже если user is None,
    # чтобы время ответа было константным (timing attack mitigation).
    # Для None используем фиктивный хэш, который заведомо не совпадёт.
    password_ok = verify_password(
        payload.password,
        user.hashed_password if user else _DUMMY_HASH,
    )

    if user is None or not password_ok:
        # Одинаковое сообщение для обоих случаев — user enumeration protection
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Шаг 3: проверка активности аккаунта ──────────────────────────────────
    if not user.is_active:
        logger.warning("Попытка входа в заблокированный аккаунт id=%d", user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован. Обратитесь к администратору платформы",
        )

    # ── Шаг 4: обновление хэша пароля при необходимости ──────────────────────
    # needs_rehash() вернёт True, если bcrypt cost factor был повышен
    # или алгоритм хэширования устарел. Обновляем «на лету» — пользователь
    # этого не замечает, безопасность повышается автоматически.
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)
        await db.flush()
        logger.info("Хэш пароля обновлён для пользователя id=%d", user.id)

    # ── Шаг 5: выдача токенов ─────────────────────────────────────────────────
    logger.info("Успешный вход пользователя id=%d", user.id)
    return await _issue_tokens_for_user(user)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  POST /auth/refresh
# ╚══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновление access-токена",
    responses={
        200: {"description": "Новая пара токенов выдана"},
        401: {"description": "Refresh-токен недействителен или просрочен"},
        403: {"description": "Аккаунт заблокирован"},
    },
)
async def refresh_tokens(
    payload: RefreshRequest,
    db: DbSession,
) -> TokenResponse:
    """
    Выдаёт новую пару токенов в обмен на действующий refresh-токен.

    Шаги:
      1. Декодируем и верифицируем refresh-токен.
      2. Загружаем актуального пользователя из БД.
      3. Проверяем is_active.
      4. Выдаём новую пару токенов (ротация токенов).

    Ротация токенов: каждый /refresh выдаёт НОВЫЙ refresh-токен.
    Это снижает риск компрометации при утечке долгоживущего токена.
    """
    # ── Шаг 1: верификация refresh-токена ────────────────────────────────────
    try:
        token_data = decode_refresh_token(payload.refresh_token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh-токен истёк. Пожалуйста, войдите снова",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenInvalidError as exc:
        logger.warning("Попытка использования невалидного refresh-токена: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный refresh-токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Шаг 2: загрузка актуального пользователя из БД ───────────────────────
    # Не доверяем только токену — всегда проверяем текущее состояние в БД.
    # Пользователь мог быть заблокирован или удалён после выдачи токена.
    user = await _get_user_by_email(db, token_data.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Шаг 3: проверка активности ───────────────────────────────────────────
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован. Обратитесь к администратору платформы",
        )

    # ── Шаг 4: ротация токенов ────────────────────────────────────────────────
    logger.info("Ротация токенов для пользователя id=%d", user.id)
    return await _issue_tokens_for_user(user)
