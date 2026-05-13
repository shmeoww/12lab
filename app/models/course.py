"""
app/models/course.py

ORM-модель курса.

Связи:
  Course >── User         (каждый курс имеет одного владельца-преподавателя)
  Course ──< Lesson       (курс содержит много уроков)
  Course ──< Enrollment   (на курс можно записаться много раз разными студентами)
  Course ──< Test         (в рамках курса — много попыток тестирования)
  Course ──< Certificate  (за курс выдаётся много сертификатов)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.certificate import Certificate
    from app.models.enrollment import Enrollment
    from app.models.lesson import Lesson
    from app.models.test import Test
    from app.models.user import User


class Course(TimestampMixin, Base):
    """
    Курс — основная учебная единица платформы.

    Жизненный цикл: черновик (is_published=False) → опубликован (is_published=True).
    Только опубликованные курсы видны студентам в каталоге.
    """
    __tablename__ = "courses"

    # ── Первичный ключ ────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Контент ───────────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Название курса, отображаемое в каталоге",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Подробное описание курса (markdown допускается)",
    )

    # ── Статус публикации ─────────────────────────────────────────────────────
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        nullable=False,
        comment="True — курс виден всем студентам в каталоге",
    )

    # ── Внешний ключ к владельцу ──────────────────────────────────────────────
    # ondelete="RESTRICT" — нельзя удалить пользователя, у которого есть курсы
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID пользователя-преподавателя, создавшего курс",
    )

    # ── Связи ─────────────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="owned_courses",
        lazy="joined",   # JOIN при каждом SELECT курса — owner нужен почти всегда
        doc="Преподаватель, создавший курс",
    )
    lessons: Mapped[list["Lesson"]] = relationship(
        "Lesson",
        back_populates="course",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Lesson.order",   # уроки всегда отсортированы по порядку
        doc="Список уроков курса, упорядоченных по полю order",
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        "Enrollment",
        back_populates="course",
        lazy="selectin",
        cascade="all, delete-orphan",
        doc="Записи студентов на этот курс",
    )
    tests: Mapped[list["Test"]] = relationship(
        "Test",
        back_populates="course",
        lazy="selectin",
        cascade="all, delete-orphan",
        doc="Попытки прохождения теста в рамках курса",
    )
    certificates: Mapped[list["Certificate"]] = relationship(
        "Certificate",
        back_populates="course",
        lazy="selectin",
        cascade="all, delete-orphan",
        doc="Сертификаты, выданные за прохождение курса",
    )

    def __repr__(self) -> str:
        return (
            f"<Course id={self.id} title={self.title!r} "
            f"published={self.is_published}>"
        )
