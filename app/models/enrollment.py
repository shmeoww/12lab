"""
app/models/enrollment.py

ORM-модель записи студента на курс.

Связи:
  Enrollment >── User    (запись принадлежит одному студенту)
  Enrollment >── Course  (запись относится к одному курсу)

Один студент не может быть записан на один курс дважды:
ограничение UniqueConstraint("user_id", "course_id").

Поле progress: 0.0 (не начат) → 100.0 (полностью пройден).
Поле is_completed: выставляется в True при progress == 100.0 или
вручную преподавателем/системой.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base 
from app.models.mixins import _utcnow 

if TYPE_CHECKING:
    from app.models.course import Course # pragma: no cover
    from app.models.user import User # pragma: no cover

class Enrollment(Base):
    """
    Связующая сущность «студент — курс».

    Хранит прогресс и статус завершения прохождения курса.
    """
    __tablename__ = "enrollments"

    # ── Составные ограничения таблицы ─────────────────────────────────────────
    __table_args__ = (
        # Один студент — одна запись на один курс
        UniqueConstraint(
            "user_id", "course_id",
            name="uq_enrollment_user_course",
        ),
        # Прогресс допустим только в диапазоне [0.0, 100.0]
        CheckConstraint(
            "progress >= 0.0 AND progress <= 100.0",
            name="ck_enrollment_progress_range",
        ),
    )

    # ── Первичный ключ ────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Внешние ключи ─────────────────────────────────────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID студента, записанного на курс",
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID курса, на который записан студент",
    )

    # ── Дата записи ───────────────────────────────────────────────────────────
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_utcnow,
        nullable=False,
        comment="Дата и время записи на курс (UTC)",
    )

    # ── Прогресс ──────────────────────────────────────────────────────────────
    progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default="0.0",
        nullable=False,
        comment="Процент прохождения курса: 0.0 (начало) – 100.0 (завершено)",
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        nullable=False,
        comment="True — студент завершил курс (progress достиг 100.0)",
    )

    # ── Связи ─────────────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User",
        back_populates="enrollments",
        lazy="joined",
        doc="Студент, записанный на курс",
    )
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="enrollments",
        lazy="joined",
        doc="Курс, на который записан студент",
    )

    def __repr__(self) -> str:
        return (
            f"<Enrollment id={self.id} user_id={self.user_id} "
            f"course_id={self.course_id} progress={self.progress:.1f}%>"
        )
