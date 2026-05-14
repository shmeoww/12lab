"""
app/auth/dependencies.py

FastAPI Dependency Injection для аутентификации и авторизации.

Иерархия зависимостей
─────────────────────
                     oauth2_scheme          get_db
                           │                  │
                    ┌──────▼──────────────────▼──────┐
                    │       get_current_user          │  → User (активный)
                    └──────────────┬─────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │                                  │
         ┌──────────▼──────────┐       ┌──────────────▼──────────┐
         │ get_current_active  │       │    get_current_admin     │
         │      _user          │       │                          │
         │  (явная аннотация   │       │  (требует is_admin=True) │
         │   авторизации)      │       │                          │
         └─────────────────────┘       └──────────────────────────┘

Использование в роутерах
─────────────────────────
  # Любой авторизованный пользователь:
  async def get_me(user: CurrentUser) -> UserResponse: ...

  # Только администратор:
  async def list_all_users(user: AdminUser) -> list[UserResponse]: ...

  # С явным Depends (если нужна зависимость, но объект не используется):
  async def some_endpoint(_: User = Depends(get_current_active_user)): ...
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    TokenDecodeError,
    TokenExpiredError,
    TokenInvalidError,
    decode_token,
)
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  OAUTH2 СХЕМА
# ╚══════════════════════════════════════════════════════════════════════════════

# tokenUrl сообщает Swagger UI, куда слать форму для получения токена.
# auto_error=True (по умолчанию): FastAPI сам вернёт 401, если заголовок
# Authorization отсутствует полностью — до вызова нашей функции.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scheme_name="JWT Bearer",
    description="JWT access-токен. Получить через POST /api/v1/auth/login",
)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ГОТОВЫЕ HTTP-ИСКЛЮЧЕНИЯ (переиспользуются во всех dependency)
# ╚══════════════════════════════════════════════════════════════════════════════

# Выносим в константы, чтобы не конструировать объект на каждый запрос
# и держать тексты ошибок в одном месте.

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось подтвердить учётные данные. Пожалуйста, войдите снова",
    headers={"WWW-Authenticate": "Bearer"},
)

_TOKEN_EXPIRED_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Срок действия токена истёк. Пожалуйста, войдите снова",
    headers={"WWW-Authenticate": "Bearer"},
)

_INACTIVE_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Аккаунт заблокирован. Обратитесь к администратору платформы",
)

_ADMIN_REQUIRED_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Недостаточно прав. Требуется роль администратора",
)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  1. get_current_user — базовая dependency
# ╚══════════════════════════════════════════════════════════════════════════════

async def get_current_user(
    token: Annotated[
        str,
        Depends(oauth2_scheme),
    ],
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
) -> User:
    """
    Базовая dependency аутентификации.

    Последовательность проверок:
      1. OAuth2PasswordBearer извлекает raw-токен из заголовка
         ``Authorization: Bearer <token>``.
         Если заголовок отсутствует — FastAPI сам возвращает 401
         (до вызова этой функции, т.к. auto_error=True).

      2. decode_token() верифицирует подпись, срок действия и тип токена.
         Бросает TokenExpiredError или TokenInvalidError при ошибке.

      3. По email из TokenData находим пользователя в БД.
         Если пользователь удалён после выдачи токена — 401.

      4. Проверяем is_active. Если аккаунт заблокирован — 403.

    Args:
        token: Raw JWT-строка, извлечённая из заголовка Authorization.
        db:    Async-сессия БД (из get_db dependency).

    Returns:
        ORM-объект User — аутентифицированный и активный пользователь.

    Raises:
        HTTPException 401: токен истёк, невалиден или пользователь не найден.
        HTTPException 403: аккаунт заблокирован (is_active=False).
    """
    # ── Шаг 1: декодирование и верификация токена ─────────────────────────────
    # decode_token() проверяет: подпись, exp, структуру payload и тип "access".
    # Разделяем исключения: истёкший токен и невалидный — разные UX-сообщения.
    try:
        token_data = decode_token(token, expected_type="access")
    except TokenExpiredError:
        # Токен был корректным, но истёк — подсказываем войти заново
        raise _TOKEN_EXPIRED_EXCEPTION
    except TokenInvalidError as exc:
        # Подпись сломана, структура неверна или тип не "access"
        logger.warning("Попытка использования невалидного токена: %s", exc)
        raise _CREDENTIALS_EXCEPTION
    except TokenDecodeError:
        # Неожиданный дочерний тип — ловим как fallback
        raise _CREDENTIALS_EXCEPTION

    # ── Шаг 2: поиск пользователя в БД ───────────────────────────────────────
    # Всегда ходим в БД — не доверяем только токену.
    # Пользователь мог быть удалён или заблокирован после выдачи токена.
    result = await db.execute(
        select(User).where(User.email == token_data.email)
    )
    user: User | None = result.scalar_one_or_none()

    if user is None:
        # email в токене валиден, но пользователь удалён из БД
        logger.warning(
            "Токен содержит email несуществующего пользователя: %s",
            token_data.email,
        )
        raise _CREDENTIALS_EXCEPTION

    # ── Шаг 3: проверка активности аккаунта ──────────────────────────────────
    # 403, а не 401 — токен валиден, но доступ явно запрещён администратором
    if not user.is_active:
        raise _INACTIVE_EXCEPTION

    return user


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  2. get_current_admin — для admin-only эндпоинтов
# ╚══════════════════════════════════════════════════════════════════════════════

async def get_current_admin(
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> User:
    """
    Dependency для эндпоинтов, доступных только администраторам.

    Строится поверх get_current_user — повторная проверка токена
    и is_active НЕ нужна (get_current_user уже сделал это).

    Args:
        current_user: Аутентифицированный активный пользователь
                      (инжектируется из get_current_user).

    Returns:
        Тот же ORM-объект User, если is_admin=True.

    Raises:
        HTTPException 403: пользователь аутентифицирован, но не является
                           администратором.
    """
    if not current_user.is_admin:
        logger.warning(
            "Попытка доступа к admin-ресурсу от пользователя id=%d",
            current_user.id,
        )
        raise _ADMIN_REQUIRED_EXCEPTION

    return current_user


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  3. get_current_active_user — явная аннотация авторизации
# ╚══════════════════════════════════════════════════════════════════════════════

async def get_current_active_user(
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> User:
    """
    Явная dependency для эндпоинтов, требующих авторизации любого юзера.

    Функционально эквивалентна get_current_user, но служит семантической
    меткой в сигнатуре эндпоинта: читателю кода сразу ясно, что маршрут
    защищён и требует авторизованного пользователя.

    Применяется вместо прямого get_current_user, когда важна явность:
        # Менее явно — читателю непонятно, нужен ли активный юзер:
        user: User = Depends(get_current_user)

        # Явно — намерение очевидно из имени:
        user: ActiveUser = Depends(get_current_active_user)

    is_active уже проверен в get_current_user — здесь повтор не нужен.

    Args:
        current_user: Аутентифицированный активный пользователь.

    Returns:
        Тот же ORM-объект User без дополнительных проверок.
    """
    return current_user


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  АННОТИРОВАННЫЕ ТИПЫ — короткий синтаксис в сигнатурах эндпоинтов
# ╚══════════════════════════════════════════════════════════════════════════════
#
# Вместо многословного:
#   current_user: User = Depends(get_current_active_user)
#
# Используй краткий псевдоним:
#   current_user: ActiveUser
#
# FastAPI автоматически применит Depends из Annotated.

CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser  = Annotated[User, Depends(get_current_active_user)]
AdminUser   = Annotated[User, Depends(get_current_admin)]

# ── Примеры использования в роутерах ─────────────────────────────────────────
#
# from app.auth.dependencies import ActiveUser, AdminUser, CurrentUser
#
# @router.get("/me", response_model=UserResponse)
# async def get_me(user: ActiveUser) -> UserResponse:
#     """Профиль текущего пользователя."""
#     return UserResponse.model_validate(user)
#
# @router.get("/admin/users", response_model=list[UserResponse])
# async def list_users(
#     _admin: AdminUser,            # проверка прав, объект не используется
#     db: Annotated[AsyncSession, Depends(get_db)],
# ) -> list[UserResponse]:
#     """Список всех пользователей — только для администратора."""
#     result = await db.execute(select(User))
#     return [UserResponse.model_validate(u) for u in result.scalars()]
#
# @router.delete("/me")
# async def delete_account(user: CurrentUser, db: ...) -> None:
#     """Удаление своего аккаунта — любой авторизованный юзер."""
#     await db.delete(user)