"""
app/schemas/lesson.py

Pydantic v2 схемы для CRUD-эндпоинтов уроков.

Карта использования:
  POST   /courses/{course_id}/lessons         LessonCreate  →  LessonResponse
  GET    /courses/{course_id}/lessons         —             →  list[LessonResponse]
  GET    /courses/{course_id}/lessons/{id}    —             →  LessonResponse
  PUT    /courses/{course_id}/lessons/{id}    LessonUpdate  →  LessonResponse
  DELETE /courses/{course_id}/lessons/{id}    —             →  204 No Content
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class LessonCreate(BaseModel):
    """
    Тело запроса POST /courses/{course_id}/lessons.

    Поля:
        title   — заголовок урока (мин. 3 символа)
        content — тело урока: текст, markdown, HTML, embed-ссылки
        order   — позиция в курсе (>=1); должна быть уникальна внутри курса
    """

    title: str = Field(
        min_length=3,
        max_length=200,
        description="Заголовок урока (минимум 3 символа)",
        examples=["Введение в переменные и типы данных"],
    )
    content: str | None = Field(
        default=None,
        description="Контент урока. Поддерживается Markdown и embed-ссылки",
        examples=["## Переменные\n\nПеременная — это именованная область памяти..."],
    )
    order: int = Field(
        ge=1,
        description="Порядковый номер урока в курсе (начиная с 1). Уникален внутри курса",
        examples=[1, 2, 3],
    )


class LessonUpdate(BaseModel):
    """
    Тело запроса PUT /courses/{course_id}/lessons/{id}.

    Все поля опциональны. Пустой запрос (все None) отклоняется.

    Предупреждение о поле order: при изменении порядка убедитесь,
    что новое значение не конфликтует с другим уроком в том же курсе
    (БД вернёт IntegrityError — обработка в роутере).
    """

    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=200,
        description="Новый заголовок урока",
        examples=["Переменные, типы и операторы — полный разбор"],
    )
    content: str | None = Field(
        default=None,
        description="Новый контент урока",
    )
    order: int | None = Field(
        default=None,
        ge=1,
        description="Новый порядковый номер (должен быть уникален в курсе)",
        examples=[2],
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        """Запрещаем полностью пустой PUT-запрос."""
        if all(v is None for v in (self.title, self.content, self.order)):
            raise ValueError(
                "Необходимо передать хотя бы одно поле: "
                "'title', 'content' или 'order'"
            )
        return self


class LessonResponse(BaseModel):
    """
    Ответ API с полными данными урока.
    Строится непосредственно из ORM-объекта Lesson.
    """

    id: int = Field(description="Уникальный ID урока")
    title: str = Field(description="Заголовок урока")
    content: str | None = Field(description="Контент урока")
    order: int = Field(description="Порядковый номер в курсе")
    course_id: int = Field(description="ID курса, которому принадлежит урок")
    created_at: datetime = Field(description="Дата создания (UTC)")

    # Читаем поля напрямую из ORM-объекта
    model_config = ConfigDict(from_attributes=True)
