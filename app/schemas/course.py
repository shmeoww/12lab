"""
app/schemas/course.py

Pydantic v2 схемы для CRUD-эндпоинтов курсов.

Карта использования:
  POST   /courses         CourseCreate  →  CourseResponse
  GET    /courses         —             →  list[CourseResponse]
  GET    /courses/{id}    —             →  CourseResponse
  PUT    /courses/{id}    CourseUpdate  →  CourseResponse
  DELETE /courses/{id}    —             →  204 No Content
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class CourseCreate(BaseModel):
    """
    Тело запроса POST /courses — создание нового курса.

    Поля:
        title        — обязательный заголовок (мин. 3 символа)
        description  — необязательное описание (markdown-friendly)
        is_published — публиковать сразу? (по умолчанию False — черновик)
    """

    title: str = Field(
        min_length=3,
        max_length=200,
        description="Название курса (минимум 3 символа)",
        examples=["Основы Python для начинающих"],
    )
    description: str | None = Field(
        default=None,
        description="Подробное описание курса. Поддерживается Markdown",
        examples=["Курс охватывает синтаксис Python, ООП и работу с файлами"],
    )
    is_published: bool = Field(
        default=False,
        description="True — курс сразу виден студентам; False — черновик",
    )


class CourseUpdate(BaseModel):
    """
    Тело запроса PUT /courses/{id} — обновление курса.

    Все поля опциональны: передаются только изменяемые.
    Пустой запрос (все None) отклоняется валидатором.
    """

    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=200,
        description="Новое название курса",
        examples=["Python Advanced: декораторы и метаклассы"],
    )
    description: str | None = Field(
        default=None,
        description="Новое описание курса",
    )
    is_published: bool | None = Field(
        default=None,
        description="Изменить статус публикации",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        """Запрещаем полностью пустой PUT-запрос."""
        if all(v is None for v in (self.title, self.description, self.is_published)):
            raise ValueError(
                "Необходимо передать хотя бы одно поле: "
                "'title', 'description' или 'is_published'"
            )
        return self


class CourseResponse(BaseModel):
    """
    Ответ API с полными данными курса.
    Строится непосредственно из ORM-объекта Course.
    """

    id: int = Field(description="Уникальный ID курса")
    title: str = Field(description="Название курса")
    description: str | None = Field(description="Описание курса")
    is_published: bool = Field(description="Статус публикации")
    owner_id: int = Field(description="ID пользователя-создателя курса")
    created_at: datetime = Field(description="Дата создания (UTC)")
    updated_at: datetime = Field(description="Дата последнего обновления (UTC)")

    # Читаем поля напрямую из ORM-объекта (SQLAlchemy → Pydantic)
    model_config = ConfigDict(from_attributes=True)


class CourseListResponse(BaseModel):
    """
    Ответ для GET /courses — список курсов с метаданными пагинации.
    """

    items: list[CourseResponse] = Field(description="Список курсов на текущей странице")
    total: int = Field(description="Общее количество курсов (без пагинации)")
    skip: int = Field(description="Смещение (offset) текущей страницы")
    limit: int = Field(description="Максимальный размер страницы")
