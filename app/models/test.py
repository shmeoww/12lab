"""
app/models/test.py

ORM-модель результата теста.

Связи:
  Test >── Course  (тест относится к конкретному курсу)
  Test >── User    (тест сдаётся конкретным студентом)

Одна запись = одна попытка прохождения теста.
Для хранения истории нескольких попыток просто создаются
новые записи с тем же user_id + course_id.

Поле `score`: 0.0 – 100.0 (процент правильных ответов).
Поле `passed`: определяется бизнес-логикой (например, score >= 70).
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import _utcnow

if TYPE_CHECKING:
    from app.models.course import Course # pragma: no cover
    from app.models.user import User # pragma: no cover

class Test(Base):
    """
    Результат одной попытки прохождения теста по курсу.

    Бизнес-правило: тест считается пройденным (passed=True),
    если score >= порогового значения (обычно 70%).
    Порог не хранится в модели — это ответственность сервисного слоя.
    """
    __tablename__ = "tests"

    # ── Ограничения таблицы ───────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "score >= 0.0 AND score <= 100.0",
            name="ck_test_score_range",
        ),
    )

    # ── Первичный ключ ────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Внешние ключи ─────────────────────────────────────────────────────────
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID курса, по которому проходится тест",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID студента, сдававшего тест",
    )

    # ── Результат ─────────────────────────────────────────────────────────────
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Результат теста в процентах: 0.0 (0%) – 100.0 (100%)",
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="True — тест засчитан как успешно пройденный",
    )

    # ── Временна́я метка ───────────────────────────────────────────────────────
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_utcnow,
        nullable=False,
        comment="Дата и время прохождения теста (UTC)",
    )

    # ── Связи ─────────────────────────────────────────────────────────────────
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="tests",
        lazy="joined",
        doc="Курс, по которому проходился тест",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tests",
        lazy="joined",
        doc="Студент, сдавший тест",
    )

    def __repr__(self) -> str:
        return (
            f"<Test id={self.id} user_id={self.user_id} "
            f"course_id={self.course_id} score={self.score:.1f} passed={self.passed}>"
        )
