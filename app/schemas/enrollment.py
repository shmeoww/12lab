"""
app/schemas/enrollment.py

Pydantic v2 схемы для эндпоинтов записи на курс.

Карта использования:
  POST   /enrollments/{course_id}            →  EnrollmentResponse
  GET    /enrollments/my                     →  list[EnrollmentResponse]
  GET    /enrollments/{course_id}/progress   →  EnrollmentResponse
  DELETE /enrollments/{course_id}            →  204 No Content
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EnrollmentResponse(BaseModel):
    """
    Ответ API с данными о записи студента на курс.

    Поле progress: 0.0 (не начат) → 100.0 (полностью завершён).
    Поле is_completed: True если progress достиг 100.0.
    """

    id: int = Field(description="Уникальный ID записи")
    user_id: int = Field(description="ID студента")
    course_id: int = Field(description="ID курса")
    enrolled_at: datetime = Field(description="Дата и время записи на курс (UTC)")
    progress: float = Field(
        ge=0.0,
        le=100.0,
        description="Процент прохождения курса: 0.0 — не начат, 100.0 — завершён",
    )
    is_completed: bool = Field(description="True — курс полностью пройден")

    # from_attributes=True — строим схему прямо из ORM-объекта Enrollment
    model_config = ConfigDict(from_attributes=True)
