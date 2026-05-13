"""
app/models/user.py

ORM-модель пользователя платформы.

Связи (relationships):
  User ──< Course        (один пользователь — много созданных курсов)
  User ──< Enrollment    (один пользователь — много записей на курсы)
  User ──< Test          (один пользователь — много попыток тестов)
  User ──< Certificate   (один пользователь — много сертификатов)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    # Импорты только для type-checker'а — избегаем циклических импортов
    from app.models.certificate import Certificate
    from app.models.course import Course
    from app.models.enrollment import Enrollment
    from app.models.test import Test


class User(CreatedAtMixin, Base):
    """
    Таблица пользователей.

    Роли реализованы через булевый флаг is_admin.
    Если потребуются гранулярные права — замени на отдельную таблицу roles.
    """
    __tablename__ = "users"

    # ── Первичный ключ ────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Учётные данные ────────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Уникальный e-mail пользователя, используется как логин",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt-хэш пароля, никогда не хранить открытый пароль",
    )

    # ── Профиль ───────────────────────────────────────────────────────────────
    full_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        comment="Полное имя пользователя (необязательно)",
    )

    # ── Флаги ─────────────────────────────────────────────────────────────────
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        nullable=False,
        comment="True — администратор платформы с полным доступом",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
        nullable=False,
        comment="False — аккаунт заблокирован, авторизация запрещена",
    )

    # ── Связи (обратные стороны) ──────────────────────────────────────────────
    # back_populates связывает с полем в соответствующей модели
    # lazy="selectin" — подгружает связанные объекты одним SELECT IN-запросом

    owned_courses: Mapped[list["Course"]] = relationship(
        "Course",
        back_populates="owner",
        lazy="select",
        cascade="all, delete-orphan",
        doc="Курсы, созданные этим пользователем (роль преподавателя)",
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        "Enrollment",
        back_populates="user",
        lazy="select",
        cascade="all, delete-orphan",
        doc="Записи на курсы как студент",
    )
    tests: Mapped[list["Test"]] = relationship(
        "Test",
        back_populates="user",
        lazy="select",
        cascade="all, delete-orphan",
        doc="Все попытки прохождения тестов",
    )
    certificates: Mapped[list["Certificate"]] = relationship(
        "Certificate",
        back_populates="user",
        lazy="select",
        cascade="all, delete-orphan",
        doc="Полученные сертификаты об окончании курсов",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} is_admin={self.is_admin}>"
