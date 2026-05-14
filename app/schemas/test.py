"""
app/schemas/test.py

Pydantic v2 схемы для эндпоинтов тестирования.

Карта использования:
  POST  /courses/{course_id}/tests       TestCreate  →  TestResponse
  GET   /courses/{course_id}/tests/my    —           →  list[TestResponse]
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Порог прохождения теста — бизнес-правило, вынесено в константу.
# При изменении порога достаточно поправить одно место.
PASS_THRESHOLD: float = 60.0


class TestCreate(BaseModel):
    """
    Тело запроса POST /courses/{course_id}/tests — сдача теста.

    Студент передаёт только итоговый score.
    Поле passed вычисляется сервером: score >= PASS_THRESHOLD.

    Поле score: процент правильных ответов, от 0.0 до 100.0.
    """

    score: float = Field(
        ge=0.0,
        le=100.0,
        description=(
            f"Результат теста в процентах (0.0–100.0). "
            f"Тест считается пройденным при score >= {PASS_THRESHOLD}"
        ),
        examples=[75.0, 45.5, 100.0],
    )


class TestResponse(BaseModel):
    """
    Ответ API с результатом попытки теста.

    Одна запись = одна попытка. История попыток — это список TestResponse.
    """

    id: int = Field(description="Уникальный ID попытки теста")
    course_id: int = Field(description="ID курса")
    user_id: int = Field(description="ID студента, сдавшего тест")
    score: float = Field(description="Результат теста в процентах (0.0–100.0)")
    passed: bool = Field(
        description=f"True — тест пройден (score >= {PASS_THRESHOLD})"
    )
    taken_at: datetime = Field(description="Дата и время сдачи теста (UTC)")

    # from_attributes=True — читаем поля напрямую из ORM-объекта Test
    model_config = ConfigDict(from_attributes=True)
