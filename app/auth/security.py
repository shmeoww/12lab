"""
app/auth/security.py

Модуль безопасности: хэширование паролей и работа с JWT-токенами.

Архитектура токенов
───────────────────
  access_token   — короткоживущий (30 мин по умолчанию).
                   Передаётся в заголовке Authorization: Bearer <token>.
                   Содержит: sub (email), exp, iat, jti, type="access".

  refresh_token  — долгоживущий (7 дней по умолчанию).
                   Используется ТОЛЬКО для получения нового access-токена
                   через POST /auth/refresh.
                   Содержит: sub (email), exp, iat, jti, type="refresh".

  jti (JWT ID)   — UUID каждого токена. Позволяет отозвать конкретный токен
                   через блок-лист (реализация блок-листа — вне этого модуля).

Исключения
──────────
  TokenExpiredError     — токен просрочен (exp < now)
  TokenInvalidError     — подпись не верна, структура сломана, неверный тип
  TokenDecodeError      — базовый класс для обоих выше (удобно для except)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# ── Настройки ─────────────────────────────────────────────────────────────────
# Берём через get_settings() — не кешируем на уровне модуля,
# чтобы тесты могли подменять настройки через dependency override.
# Функция сама кеширует через @lru_cache, накладных расходов нет.

# ── Контекст bcrypt ───────────────────────────────────────────────────────────
# schemes=["bcrypt"]   — единственный активный алгоритм
# deprecated="auto"    — старые хэши (md5_crypt и т.д.) автоматически
#                        помечаются как устаревшие и требуют перехэширования
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ТИПЫ И ИСКЛЮЧЕНИЯ
# ╚══════════════════════════════════════════════════════════════════════════════

TokenType = Literal["access", "refresh"]


@dataclass(frozen=True, slots=True)
class TokenData:
    """
    Структурированные данные, извлечённые из JWT-токена.

    Используется как возвращаемый тип decode_token() — вместо сырого dict,
    чтобы IDE подсказывала поля и исключить опечатки вроде payload["Sub"].

    Атрибуты:
        email      — значение claim'а `sub` (идентификатор пользователя)
        token_type — "access" или "refresh"
        jti        — уникальный ID токена (UUID4 строка)
        exp        — время истечения (UTC, timezone-aware)
        iat        — время выпуска (UTC, timezone-aware)
    """
    email: str
    token_type: TokenType
    jti: str
    exp: datetime
    iat: datetime


class TokenDecodeError(Exception):
    """Базовый класс ошибок декодирования токена."""


class TokenExpiredError(TokenDecodeError):
    """JWT-токен существует, но его срок действия истёк."""


class TokenInvalidError(TokenDecodeError):
    """JWT-токен повреждён, подпись неверна или тип не совпадает."""


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ПАРОЛИ
# ╚══════════════════════════════════════════════════════════════════════════════

def hash_password(plain_password: str) -> str:
    """
    Хэширует пароль алгоритмом bcrypt.

    bcrypt автоматически генерирует соль и встраивает её в хэш,
    поэтому одинаковые пароли дают разные хэши — rainbow-таблицы бесполезны.

    Args:
        plain_password: Открытый пароль, полученный от пользователя.

    Returns:
        Строка вида '$2b$12$...' — хэш для сохранения в БД.

    Example:
        >>> h = hash_password("Secret123")
        >>> h.startswith("$2b$")
        True
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Сравнивает открытый пароль с bcrypt-хэшом.

    Использует константное время сравнения (timing-safe) — защита от
    timing-атак, когда злоумышленник измеряет время ответа сервера.

    Args:
        plain_password:   Пароль из запроса (открытый текст).
        hashed_password:  Хэш из базы данных.

    Returns:
        True  — пароль совпадает.
        False — пароль неверен.

    Example:
        >>> h = hash_password("Secret123")
        >>> verify_password("Secret123", h)
        True
        >>> verify_password("Wrong", h)
        False
    """
    return _pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """
    Проверяет, нужно ли перехэшировать пароль.

    Возвращает True, если хэш был создан с устаревшими параметрами
    (старый cost factor bcrypt, deprecated алгоритм и т.д.).
    Вызывай после успешного verify_password и обновляй хэш в БД.

    Example:
        if verify_password(plain, user.hashed_password):
            if needs_rehash(user.hashed_password):
                user.hashed_password = hash_password(plain)
    """
    return _pwd_context.needs_update(hashed_password)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  JWT — СОЗДАНИЕ
# ╚══════════════════════════════════════════════════════════════════════════════

def _build_token(
    email: str,
    token_type: TokenType,
    expires_delta: timedelta,
) -> str:
    """
    Внутренняя функция сборки JWT-токена.

    Параметры payload:
        sub   — Subject: email пользователя (RFC 7519 §4.1.2)
        exp   — Expiration Time: unix-timestamp истечения (RFC 7519 §4.1.4)
        iat   — Issued At: unix-timestamp выпуска (RFC 7519 §4.1.6)
        jti   — JWT ID: уникальный UUID токена (RFC 7519 §4.1.7)
        type  — кастомный claim: "access" или "refresh"

    Args:
        email:          E-mail пользователя (идентификатор субъекта).
        token_type:     Тип токена: "access" или "refresh".
        expires_delta:  Время жизни токена.

    Returns:
        Подписанный JWT-токен в компактном представлении (строка).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    payload: dict[str, str | datetime] = {
        "sub": email,           # кому выдан токен
        "type": token_type,     # тип: access / refresh
        "jti": str(uuid.uuid4()),  # уникальный ID (для блок-листа)
        "iat": now,             # когда выпущен
        "exp": now + expires_delta,  # когда истекает
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def create_access_token(email: str) -> str:
    """
    Выпускает JWT access-токен для пользователя.

    Токен короткоживущий (ACCESS_TOKEN_EXPIRE_MINUTES из .env).
    Передаётся клиентом в заголовке:
        Authorization: Bearer <token>

    Args:
        email: E-mail пользователя — используется как sub claim.

    Returns:
        Подписанный JWT access-токен.

    Example:
        token = create_access_token("user@example.com")
        # → "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    """
    settings = get_settings()
    return _build_token(
        email=email,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(email: str) -> str:
    """
    Выпускает JWT refresh-токен для пользователя.

    Токен долгоживущий (REFRESH_TOKEN_EXPIRE_DAYS из .env).
    Используется ТОЛЬКО в эндпоинте POST /auth/refresh для получения
    нового access-токена. Не должен использоваться для авторизации запросов.

    Args:
        email: E-mail пользователя — используется как sub claim.

    Returns:
        Подписанный JWT refresh-токен.
    """
    settings = get_settings()
    return _build_token(
        email=email,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def create_token_pair(email: str) -> tuple[str, str]:
    """
    Выпускает пару токенов: (access_token, refresh_token).

    Удобная обёртка для эндпоинта POST /auth/login.

    Args:
        email: E-mail аутентифицированного пользователя.

    Returns:
        Кортеж (access_token, refresh_token).

    Example:
        access, refresh = create_token_pair("user@example.com")
        return {"access_token": access, "refresh_token": refresh}
    """
    return (
        create_access_token(email),
        create_refresh_token(email),
    )


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  JWT — ДЕКОДИРОВАНИЕ
# ╚══════════════════════════════════════════════════════════════════════════════

def decode_token(token: str, expected_type: TokenType = "access") -> TokenData:
    """
    Декодирует и полностью верифицирует JWT-токен.

    Проверяет:
      ✓ Подпись (SECRET_KEY + ALGORITHM)
      ✓ Срок действия (exp claim)
      ✓ Наличие обязательных полей (sub, jti, iat, exp, type)
      ✓ Тип токена совпадает с expected_type

    Args:
        token:         JWT-строка (из заголовка Authorization или тела запроса).
        expected_type: Ожидаемый тип токена: "access" (по умолчанию) или "refresh".

    Returns:
        TokenData — структурированные данные из payload.

    Raises:
        TokenExpiredError: Токен существует, но его срок истёк.
        TokenInvalidError: Подпись неверна, структура сломана или тип неверен.

    Example:
        try:
            data = decode_token(token)
            # data.email → "user@example.com"
        except TokenExpiredError:
            raise HTTPException(401, "Токен истёк")
        except TokenInvalidError:
            raise HTTPException(401, "Токен недействителен")
    """
    settings = get_settings()

    try:
        raw: dict = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except ExpiredSignatureError:
        # jose выбрасывает это ДО того, как даст нам payload —
        # перехватываем отдельно, чтобы дать информативное сообщение
        raise TokenExpiredError("Срок действия токена истёк")
    except JWTError as exc:
        raise TokenInvalidError(f"Токен недействителен: {exc}") from exc

    # ── Валидация обязательных полей ─────────────────────────────────────────
    email: str | None = raw.get("sub")
    token_type: str | None = raw.get("type")
    jti: str | None = raw.get("jti")
    exp_raw = raw.get("exp")
    iat_raw = raw.get("iat")

    if not email:
        raise TokenInvalidError("Токен не содержит поле 'sub' (email)")
    if not jti:
        raise TokenInvalidError("Токен не содержит поле 'jti'")
    if exp_raw is None or iat_raw is None:
        raise TokenInvalidError("Токен не содержит временны́е метки 'exp'/'iat'")

    # ── Проверка типа токена ──────────────────────────────────────────────────
    if token_type != expected_type:
        raise TokenInvalidError(
            f"Ожидался токен типа '{expected_type}', получен '{token_type}'"
        )

    # ── Преобразование unix-timestamp → datetime ──────────────────────────────
    exp = datetime.fromtimestamp(exp_raw, tz=timezone.utc)
    iat = datetime.fromtimestamp(iat_raw, tz=timezone.utc)

    return TokenData(
        email=email,
        token_type=token_type,  # type: ignore[arg-type]
        jti=jti,
        exp=exp,
        iat=iat,
    )


def decode_refresh_token(token: str) -> TokenData:
    """
    Удобная обёртка для декодирования refresh-токена.

    Вызывай в эндпоинте POST /auth/refresh.

    Args:
        token: JWT refresh-токен.

    Returns:
        TokenData с token_type="refresh".

    Raises:
        TokenExpiredError, TokenInvalidError — аналогично decode_token().
    """
    return decode_token(token, expected_type="refresh")