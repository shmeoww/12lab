# Prompt Log
## Задание 1, повышенная сложность:  Создание полноценного веб-приложения.
### Промпт 1
**Инструмент:** Claude
**Промпт:** "Ты — senior Python разработчик. Создай базовую структуру FastAPI проекта 
для платформы онлайн-обучения со следующими требованиями:
- База данных: SQLite через SQLAlchemy
- Конфигурация через .env файл (python-dotenv)
- Alembic для миграций
Нужно:
1. requirements.txt со всеми зависимостями
2. app/database.py — подключение к SQLite, создание сессии
3. app/main.py — базовый FastAPI app с CORS, подключением роутеров
4. .env.example — шаблон переменных окружения
Покрой код type hints, добавь комментарии."
**Результат:**Получила базовую структуру проекта, database.py с сессиями SQLAlchemy, main.py с CORS middleware, requirements.txt.
### Промпт 2
**Инструмент:** Claude
**Промпт:** "Ты — senior Python разработчик. Создай SQLAlchemy 2.x модели для платформы 
онлайн-обучения. Используй асинхронный подход (async SQLAlchemy).
Модели:
1. User: id, email (уникальный), hashed_password, full_name, is_admin (bool, default False),
is_active (bool, default True), created_at
2. Course: id, title, description, owner_id (FK -> users), is_published (bool, default False),
created_at, updated_at
3. Lesson: id, title, content, order (порядковый номер урока), course_id (FK -> courses),
created_at
4. Enrollment: id, user_id (FK -> users), course_id (FK -> courses), enrolled_at,
progress (float, 0.0-100.0, default 0.0), is_completed (bool, default False)
5. Test: id, course_id (FK -> courses), user_id (FK -> users), score (float),
passed (bool), taken_at
6. Certificate: id, user_id (FK -> users), course_id (FK -> courses),
issued_at, certificate_number (уникальный)
Требования:
- Все модели наследуются от Base из app.database
- Связи между моделями через relationship()
- Все поля с правильными типами и constraints
- created_at с автоматическим значением datetime.utcnow
- Покрой код type hints и комментариями"
**Результат:**Получила все 6 моделей + mixins.py + __init__.py.
### Промпт 3
**Инструмент:** Claude
**Промпт:** ""
**Результат:**