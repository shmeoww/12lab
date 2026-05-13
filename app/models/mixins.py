"""
app/models/mixins.py

Переиспользуемые миксины для ORM-моделей.
Подключаются через множественное наследование перед Base:

    class Course(TimestampMixin, Base):
        ...
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    """Возвращает текущее время UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


class CreatedAtMixin:
    """
    Добавляет поле created_at с автоматическим заполнением
    при первой вставке записи.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        # server_default — значение выставляет сама БД (надёжнее при bulk insert)
        server_default=func.now(),
        # default — значение выставляет Python при создании объекта
        default=_utcnow,
        nullable=False,
    )


class TimestampMixin(CreatedAtMixin):
    """
    Добавляет created_at и updated_at.
    updated_at обновляется автоматически при каждом UPDATE через onupdate.
    """
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
