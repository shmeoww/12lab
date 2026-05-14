"""
app/schemas/user.py

Pydantic v2 схемы для эндпоинтов пользователей и аутентификации.

Карта использования
───────────────────
  Регистрация:   UserCreate  →  [POST /auth/register]  →  UserResponse
  Вход:          UserLogin   →  [POST /auth/login]      →  TokenResponse
  Обновление:    UserUpdate  →  [PATCH /users/me]       →  UserResponse
  Обновл. токена: RefreshRequest → [POST /auth/refresh] → TokenResponse
"""

import re
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from typing_extensions import Self


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ВСПОМОГАТЕЛЬНЫЕ КОНСТАНТЫ
# ╚══════════════════════════════════════════════════════════════════════════════

# Минимальные требования к паролю
_PASSWORD_MIN_LEN: int = 8
_PASSWORD_MAX_LEN: int = 128

# Регулярка: хотя бы одна цифра + одна заглавная буква
_PASSWORD_DIGIT_RE = re.compile(r"\d")
_PASSWORD_UPPER_RE = re.compile(r"[A-Z]")


def _validate_password_strength(password: str) -> str:
    """
    Переиспользуемая функция валидации надёжности пароля.

    Требования:
      - минимум 8 символов (задаётся через Field(min_length=...))
      - хотя бы одна цифра
      - хотя бы одна заглавная латинская буква

    Выделена отдельно, чтобы не дублировать логику
    в UserCreate и UserUpdate.
    """
    if not _PASSWORD_DIGIT_RE.search(password):
        raise ValueError("Пароль должен содержать хотя бы одну цифру (0–9)")
    if not _PASSWORD_UPPER_RE.search(password):
        raise ValueError("Пароль должен содержать хотя бы одну заглавную букву (A–Z)")
    return password


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  СХЕМЫ ПОЛЬЗОВАТЕЛЯ
# ╚══════════════════════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    """
    Тело запроса POST /auth/register.

    Поля:
        email     — будет нормализован в нижний регистр
        password  — открытый текст, передаётся только сюда и нигде больше
        full_name — необязательное отображаемое имя
    """

    email: EmailStr = Field(
        description="E-mail пользователя (уникальный логин на платформе)",
        examples=["student@example.com"],
    )
    password: str = Field(
        min_length=_PASSWORD_MIN_LEN,
        max_length=_PASSWORD_MAX_LEN,
        description=(
            f"Пароль: {_PASSWORD_MIN_LEN}–{_PASSWORD_MAX_LEN} символов, "
            "минимум одна цифра и одна заглавная буква"
        ),
        examples=["Secure123"],
    )
    full_name: str | None = Field(
        default=None,
        max_length=150,
        description="Полное имя пользователя (отображается в профиле)",
        examples=["Иван Иванов"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        """Приводим email к нижнему регистру до стандартной валидации EmailStr."""
        return v.strip().lower()

    @field_validator("password", mode="after")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, v: str | None) -> str | None:
        """Убираем лишние пробелы; пустую строку превращаем в None."""
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


class UserLogin(BaseModel):
    """
    Тело запроса POST /auth/login.

    Намеренно минимальна — только то, что нужно для аутентификации.
    """

    email: EmailStr = Field(
        description="E-mail, указанный при регистрации",
        examples=["student@example.com"],
    )
    password: str = Field(
        min_length=1,  # Не проверяем сложность — это уже было при регистрации
        max_length=_PASSWORD_MAX_LEN,
        description="Пароль пользователя",
        examples=["Secure123"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    """
    Ответ API с данными пользователя.

    НИКОГДА не содержит пароль или его хэш.
    Используется как response_model для регистрации и профиля.
    """

    id: int = Field(description="Уникальный числовой ID пользователя")
    email: str = Field(description="E-mail пользователя")
    full_name: str | None = Field(description="Полное имя (может быть не задано)")
    is_admin: bool = Field(description="True — администратор платформы")
    is_active: bool = Field(description="False — аккаунт заблокирован")
    created_at: datetime = Field(description="Дата и время регистрации (UTC)")

    # from_attributes=True позволяет строить схему прямо из ORM-объекта:
    #   UserResponse.model_validate(user_orm_instance)
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """
    Тело запроса PATCH /users/me — частичное обновление профиля.

    Все поля опциональны: передаются только те, которые нужно изменить.
    """

    full_name: str | None = Field(
        default=None,
        max_length=150,
        description="Новое полное имя (None — не менять)",
        examples=["Пётр Петров"],
    )
    password: str | None = Field(
        default=None,
        min_length=_PASSWORD_MIN_LEN,
        max_length=_PASSWORD_MAX_LEN,
        description="Новый пароль (None — не менять)",
        examples=["NewSecure456"],
    )

    @field_validator("password", mode="after")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_password_strength(v)

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        """Запрещаем пустой PATCH — хотя бы одно поле должно быть передано."""
        if self.full_name is None and self.password is None:
            raise ValueError(
                "Необходимо передать хотя бы одно поле: 'full_name' или 'password'"
            )
        return self


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  СХЕМЫ ТОКЕНОВ
# ╚══════════════════════════════════════════════════════════════════════════════

class TokenResponse(BaseModel):
    """
    Ответ эндпоинтов /auth/login и /auth/refresh.

    Стандартный OAuth2-совместимый формат ответа.
    Клиент сохраняет access_token для авторизации запросов
    и refresh_token для автоматического обновления сессии.
    """

    access_token: str = Field(
        description="JWT access-токен. Добавлять в заголовок: Authorization: Bearer <token>"
    )
    refresh_token: str = Field(
        description="JWT refresh-токен. Использовать ТОЛЬКО для обновления access-токена"
    )
    token_type: str = Field(
        default="bearer",
        description="Тип токена (всегда 'bearer' согласно OAuth2)",
    )


class RefreshRequest(BaseModel):
    """
    Тело запроса POST /auth/refresh.

    Принимает refresh_token и возвращает новую пару токенов.
    """

    refresh_token: str = Field(
        description="Действующий JWT refresh-токен, полученный при логине"
    )
