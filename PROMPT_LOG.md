# Prompt Log
## Задание 1, повышенная сложность:  Создание полноценного веб-приложения.
### Промпт 1
**Инструмент:** Claude
**Промпт:** "Ты — senior Python разработчик. Создай базовую структуру FastAPI проекта для платформы онлайн-обучения со следующими требованиями:
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
**Промпт:** "Ты — senior Python разработчик. Создай SQLAlchemy 2.x модели для платформы онлайн-обучения. Используй асинхронный подход (async SQLAlchemy).
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
**Промпт:** "Ты — senior Python разработчик. Создай модуль app/auth/security.py для платформы онлайн-обучения на FastAPI.
Нужно реализовать:
1. Хэширование пароля через passlib (bcrypt)
2. Проверку пароля (verify_password)
3. Создание JWT access токена через python-jose
4. Декодирование и верификацию JWT токена
Настройки (SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES) 
брать из app.config через get_settings().
Токен должен содержать: sub (email пользователя), exp (время истечения). Покрой код type hints и комментариями."
**Результат:**Получила security.py с хэшированием паролей, созданием и верификацией
JWT.
### Промпт 4
**Инструмент:** Claude
**Промпт:** "Ты — senior Python разработчик. Создай эндпоинты аутентификации для платформы онлайн-обучения на FastAPI.
Контекст проекта:
- Асинхронный SQLAlchemy (AsyncSession)
- Модель User в app/models/user.py с полями: 
  id, email, hashed_password, full_name, is_admin, is_active, created_at
- JWT утилиты в app/auth/security.py:
  hash_password(), verify_password(), create_token_pair(), needs_rehash()
  Исключения: TokenExpiredError, TokenInvalidError
- get_db() dependency в app/database.py возвращает AsyncSession
- get_settings() в app/config.py

Нужно создать:
1. app/schemas/user.py — Pydantic v2 схемы:
   - UserCreate: email, password (min 8 символов), full_name (опционально)
   - UserLogin: email, password
   - UserResponse: id, email, full_name, is_admin, is_active, created_at
   - TokenResponse: access_token, refresh_token, token_type="bearer"

2. app/routers/auth.py — роутер с эндпоинтами:
   - POST /auth/register: регистрация нового пользователя
     * Проверить что email не занят (409 если занят)
     * Захэшировать пароль
     * Сохранить в БД
     * Вернуть UserResponse
   - POST /auth/login: вход
     * Найти пользователя по email (401 если не найден)
     * Проверить пароль (401 если неверный)
     * Проверить is_active (403 если заблокирован)
     * Вызвать needs_rehash и обновить хэш если нужно
     * Вернуть TokenResponse с парой токенов
Требования: async/await везде, обработка ошибок через HTTPException, type hints, комментарии."
**Результат:**Получила schemas/user.py (6 схем) и routers/auth.py (register, login, refresh) + обновлённый main.py с подключённым роутером.
### Промпт 5
**Инструмент:** Claude
**Промпт:** "Ты — senior Python разработчик. Создай файл app/auth/dependencies.py для платформы онлайн-обучения на FastAPI.
Контекст проекта:
- Асинхронный SQLAlchemy (AsyncSession)
- Модель User в app/models/user.py
- JWT утилиты в app/auth/security.py:
  decode_token(), TokenExpiredError, TokenInvalidError
- get_db() в app/database.py возвращает AsyncSession

Нужно создать три dependency-функции:
1. get_current_user(token, db) → User
   - Извлекает Bearer токен из заголовка Authorization
   - Декодирует JWT через decode_token()
   - Находит пользователя в БД по email из токена
   - Проверяет is_active
   - Возвращает ORM-объект User
   - 401 если токен невалидный/просрочен или пользователь не найден
   - 403 если is_active=False

2. get_current_admin(current_user) → User
   - Зависит от get_current_user
   - Проверяет is_admin=True
   - 403 если не админ

3. get_current_active_user(current_user) → User
   - Зависит от get_current_user
   - Просто возвращает пользователя (is_active уже проверен выше)
   - Используется как явная аннотация что эндпоинт требует авторизации
Требования: OAuth2PasswordBearer для извлечения токена, async/await везде, type hints, комментарии."
**Результат:** Получила dependencies.py с тремя dependency-функциями и type aliases CurrentUser, ActiveUser, AdminUser.
### Промпт 6
**Инструмент:** Claude
**Промпт:** "Ты — senior Python разработчик.  Создай CRUD эндпоинты для курсов и уроков для платформы онлайн-обучения на FastAPI.
Контекст проекта:
- Асинхронный SQLAlchemy (AsyncSession)
- Модели: Course, Lesson в app/models/
- Dependency aliases в app/auth/dependencies.py:
  ActiveUser, AdminUser (Annotated типы)
- get_db() в app/database.py
- DbSession = Annotated[AsyncSession, Depends(get_db)]

Нужно создать:
1. app/schemas/course.py — Pydantic v2 схемы:
   - CourseCreate: title (min 3), description (опционально), is_published (default False)
   - CourseUpdate: все поля опциональны
   - CourseResponse: id, title, description, is_published, owner_id, created_at, updated_at

2. app/schemas/lesson.py — Pydantic v2 схемы:
   - LessonCreate: title (min 3), content (опционально), order (int >= 1)
   - LessonUpdate: все поля опциональны
   - LessonResponse: id, title, content, order, course_id, created_at

3. app/routers/courses.py — роутер prefix="/courses":
   - GET /courses — список опубликованных курсов (для всех)
   - GET /courses/{id} — детали курса (для всех)
   - POST /courses — создать курс (только AdminUser)
   - PUT /courses/{id} — обновить курс (только AdminUser)
   - DELETE /courses/{id} — удалить курс (только AdminUser)

4. app/routers/lessons.py — роутер prefix="/courses/{course_id}/lessons":
   - GET /courses/{course_id}/lessons — список уроков курса (ActiveUser)
   - GET /courses/{course_id}/lessons/{id} — детали урока (ActiveUser)
   - POST /courses/{course_id}/lessons — создать урок (AdminUser)
   - PUT /courses/{course_id}/lessons/{id} — обновить урок (AdminUser)
   - DELETE /courses/{course_id}/lessons/{id} — удалить урок (AdminUser)

Требования:
- 404 если курс/урок не найден
- async/await везде
- type hints и комментарии
- from_attributes=True в response схемах"
**Результат:** Получила schemas (course.py, lesson.py) и роутеры (courses.py, lessons.py) + обновлённый main.py.