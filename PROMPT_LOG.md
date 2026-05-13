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