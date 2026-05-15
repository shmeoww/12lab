"""
app/models/certificate.py

ORM-модель сертификата об окончании курса.

Связи:
  Certificate >── User    (сертификат выдаётся конкретному студенту)
  Certificate >── Course  (сертификат выдаётся за конкретный курс)

Один студент получает не более одного сертификата за курс:
ограничение UniqueConstraint("user_id", "course_id").

Поле `certificate_number` глобально уникально — используется
в URL верификации: /verify/{certificate_number}
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import _utcnow

if TYPE_CHECKING:
    from app.models.course import Course # pragma: no cover
    from app.models.user import User # pragma: no cover

def _generate_certificate_number() -> str:
    """
    Генерирует уникальный номер сертификата в формате UUID4.
    Пример: 'CERT-550e8400-e29b-41d4-a716-446655440000'
    """
    return f"CERT-{uuid.uuid4()}"


class Certificate(Base):
    """
    Сертификат об успешном окончании курса.

    Выдаётся автоматически при достижении is_completed=True в Enrollment
    и passed=True в последней попытке Test (бизнес-логика в сервисном слое).
    """
    __tablename__ = "certificates"

    # ── Ограничения таблицы ───────────────────────────────────────────────────
    __table_args__ = (
        # Студент получает максимум один сертификат за один курс
        UniqueConstraint(
            "user_id", "course_id",
            name="uq_certificate_user_course",
        ),
    )

    # ── Первичный ключ ────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ── Внешние ключи ─────────────────────────────────────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID студента, получившего сертификат",
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID курса, за прохождение которого выдан сертификат",
    )

    # ── Дата выдачи ───────────────────────────────────────────────────────────
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_utcnow,
        nullable=False,
        comment="Дата и время выдачи сертификата (UTC)",
    )

    # ── Уникальный номер ──────────────────────────────────────────────────────
    certificate_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        default=_generate_certificate_number,
        comment="Глобально уникальный идентификатор для верификации: CERT-<uuid4>",
    )

    # ── Связи ─────────────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User",
        back_populates="certificates",
        lazy="joined",
        doc="Студент, которому выдан сертификат",
    )
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="certificates",
        lazy="joined",
        doc="Курс, за который выдан сертификат",
    )

    def __repr__(self) -> str:
        return (
            f"<Certificate id={self.id} "
            f"number={self.certificate_number!r} "
            f"user_id={self.user_id} course_id={self.course_id}>"
        )
