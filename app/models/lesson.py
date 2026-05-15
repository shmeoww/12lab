"""
app/models/lesson.py

ORM-модель урока внутри курса.

Связи:
  Lesson >── Course  (урок принадлежит ровно одному курсу)

Порядок уроков задаётся полем `order` (1, 2, 3...).
При удалении курса все его уроки удаляются каскадно (cascade в Course.lessons).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.course import Course # pragma: no cover


class Lesson(CreatedAtMixin, Base):
    """
    Урок — минимальная единица учебного контента.

    Поле `order` задаёт позицию урока в курсе.
    Пара (course_id, order) уникальна: два урока в одном курсе
    не могут иметь одинаковый порядковый номер.
    """
    __tablename__ = "lessons"

    # ── Составные ограничения таблицы ─────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "course_id", "order",
            name="uq_lesson_course_order",
        ),
    )

    # ── Первичный ключ ────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Контент ───────────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Заголовок урока",
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Основной контент урока: текст, markdown, HTML или embed-ссылка",
    )

    # ── Порядковый номер ──────────────────────────────────────────────────────
    order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Порядковый номер урока внутри курса (начинается с 1)",
    )

    # ── Внешний ключ ─────────────────────────────────────────────────────────
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID курса, которому принадлежит урок",
    )

    # ── Связи ─────────────────────────────────────────────────────────────────
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="lessons",
        lazy="joined",
        doc="Курс, которому принадлежит этот урок",
    )

    def __repr__(self) -> str:
        return (
            f"<Lesson id={self.id} order={self.order} "
            f"title={self.title!r} course_id={self.course_id}>"
        )
