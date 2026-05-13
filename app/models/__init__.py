"""
app/models/__init__.py

Реэкспорт всех ORM-моделей.

ВАЖНО: все модели должны быть импортированы здесь, чтобы:
  1. SQLAlchemy зарегистрировал их в Base.metadata
  2. Alembic обнаружил изменения при `alembic revision --autogenerate`
  3. Circular import'ы разрешались корректно через TYPE_CHECKING
"""

from app.models.certificate import Certificate
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.test import Test
from app.models.user import User

__all__: list[str] = [
    "User",
    "Course",
    "Lesson",
    "Enrollment",
    "Test",
    "Certificate",
]
