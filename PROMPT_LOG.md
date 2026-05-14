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
### Промпт 7
**Инструмент:** Claude
**Промпт:** "Ты — senior Python разработчик. Создай эндпоинты для записи на курс и прохождения тестов для платформы онлайн-обучения на FastAPI.
Контекст проекта:
- Асинхронный SQLAlchemy (AsyncSession)
- Модели: Course, Enrollment, Test, Lesson в app/models/
- Dependency aliases в app/auth/dependencies.py:
  ActiveUser, AdminUser
- DbSession = Annotated[AsyncSession, Depends(get_db)]

Нужно создать:
1. app/schemas/enrollment.py — Pydantic v2 схемы:
   - EnrollmentResponse: id, user_id, course_id, enrolled_at,
     progress (float), is_completed

2. app/schemas/test.py — Pydantic v2 схемы:
   - TestCreate: score (float, 0-100)
   - TestResponse: id, course_id, user_id, score, passed, taken_at

3. app/routers/enrollments.py — роутер prefix="/enrollments":
   - POST /enrollments/{course_id} — записаться на курс (ActiveUser)
     * Проверить что курс существует и опубликован (404/400)
     * Проверить что студент ещё не записан (409)
     * Создать Enrollment
     * Вернуть EnrollmentResponse
   - GET /enrollments/my — мои записи (ActiveUser)
     * Вернуть список курсов на которые записан текущий пользователь
   - GET /enrollments/{course_id}/progress — мой прогресс по курсу (ActiveUser)
     * Вернуть EnrollmentResponse с текущим прогрессом
   - DELETE /enrollments/{course_id} — отписаться от курса (ActiveUser)

4. app/routers/tests.py — роутер prefix="/courses/{course_id}/tests":
   - POST /courses/{course_id}/tests — сдать тест (ActiveUser)
     * Проверить что студент записан на курс (403 если нет)
     * Сохранить результат теста (passed = score >= 60)
     * Если passed=True — обновить progress в Enrollment
       (прогресс = количество пройденных тестов / общее уроков * 100)
     * Если progress=100 — установить is_completed=True
     * Вернуть TestResponse
   - GET /courses/{course_id}/tests/my — мои результаты тестов по курсу (ActiveUser)
Требования: async/await везде, обработка ошибок через HTTPException, type hints, комментарии."
**Результат:** Получила schemas (enrollment.py, test.py) и роутеры (enrollments.py, tests.py) + обновлённый main.py.
### Промпт 8
**Инструмент:** Claude
**Промпт:** "Ты — senior Python разработчик. Создай эндпоинты для сертификатов для платформы онлайн-обучения на FastAPI.
Контекст проекта:
- Асинхронный SQLAlchemy (AsyncSession)
- Модели: Certificate, Enrollment в app/models/
- Certificate имеет поля: id, user_id, course_id, issued_at, certificate_number (уникальный)
- Enrollment имеет поле is_completed (bool)
- Dependency aliases: ActiveUser, AdminUser в app/auth/dependencies.py
- DbSession = Annotated[AsyncSession, Depends(get_db)]

Нужно создать:
1. app/schemas/certificate.py — Pydantic v2 схемы:
   - CertificateResponse: id, user_id, course_id, issued_at, certificate_number

2. app/routers/certificates.py — роутер prefix="/certificates":
   - POST /certificates/{course_id} — получить сертификат (ActiveUser)
     * Проверить что студент завершил курс (is_completed=True в Enrollment)
       иначе 400 с сообщением о текущем прогрессе
     * Проверить что сертификат ещё не выдавался (409 если уже есть)
     * Сгенерировать уникальный certificate_number формата:
       CERT-{YEAR}-{UUID4 первые 8 символов верхним регистром}
       Пример: CERT-2024-A1B2C3D4
     * Сохранить Certificate в БД
     * Вернуть CertificateResponse
   - GET /certificates/my — мои сертификаты (ActiveUser)
   - GET /certificates/{certificate_number} — проверить сертификат (без авторизации)
     * Публичный эндпоинт для верификации сертификата по номеру
Требования: async/await везде, обработка ошибок через HTTPException, type hints, комментарии."
**Результат:** Получила schemas/certificate.py (2 схемы) и routers/certificates.py (3 эндпоинта) + обновлённый main.py.
### Промпт 9
**Инструмент:** Claude
**Промпт:** "Ты — senior Python разработчик. Создай роутер аналитики для платформы онлайн-обучения на FastAPI.
Контекст проекта:
- Асинхронный SQLAlchemy (AsyncSession)
- Модели: User, Course, Lesson, Enrollment, Test, Certificate в app/models/
- Dependency aliases: ActiveUser, AdminUser в app/auth/dependencies.py
- DbSession = Annotated[AsyncSession, Depends(get_db)]

Нужно создать app/routers/analytics.py — роутер prefix="/analytics":
1. GET /analytics/stats — общая статистика платформы (AdminUser)
   Вернуть:
   - total_users: количество пользователей
   - total_courses: количество курсов
   - total_enrollments: количество записей на курсы
   - total_certificates: количество выданных сертификатов
   - total_lessons: количество уроков

2. GET /analytics/top-courses — топ-5 курсов по записям (AdminUser)
   Вернуть список: course_id, title, enrollment_count
   Отсортировать по убыванию enrollment_count

3. GET /analytics/my-stats — личная статистика студента (ActiveUser)
   Вернуть:
   - enrolled_courses: количество курсов на которые записан
   - completed_courses: количество завершённых курсов
   - certificates_count: количество полученных сертификатов
   - average_score: средний балл по всем тестам (None если тестов нет)
   - total_tests_taken: количество сданных тестов

Все ответы — отдельные Pydantic v2 схемы прямо в этом же файле (не нужен отдельный schemas/analytics.py). Требования: async/await, func.count/func.avg из sqlalchemy, type hints, комментарии."
**Результат:**Получила routers/analytics.py (3 эндпоинта) и обновлённый main.py.
### Промпт 10
**Инструмент:** Claude
**Промпт:** "Создай простой одностраничный фронтенд (один файл static/index.html) для платформы онлайн-обучения. Используй только vanilla JS и CSS — без фреймворков, без npm.
API работает на http://127.0.0.1:8000/api/v1
JWT токен хранить в localStorage под ключом "access_token".
Страницы (переключаются через show/hide div):
1. Страница Auth (по умолчанию если не авторизован):
   - Две вкладки: Вход / Регистрация
   - Вход: поля email, password → POST /auth/login
   - Регистрация: поля email, password, full_name → POST /auth/register
   - После успешного входа сохранить токен и перейти на страницу курсов

2. Страница Курсы (после авторизации):
   - Навбар: название платформы, кнопка "Мой профиль", кнопка "Выйти"
   - Список курсов → GET /courses/ (карточки с названием и описанием)
   - Кнопка "Записаться" на каждой карточке → POST /enrollments/{course_id}

3. Страница Профиль:
   - Личная статистика → GET /analytics/my-stats
   - Список моих курсов → GET /enrollments/my
   - Кнопка "Назад к курсам"

Требования:
- Минималистичный дизайн, чистый CSS без библиотек
- Обработка ошибок (показывать сообщение если запрос упал)
- Кнопка выйти очищает localStorage и возвращает на Auth страницу
- Адаптивная вёрстка не нужна"
**Результат:** Получила index.html с тремя страницами (Auth, Courses, Profile),скелетон-загрузкой, toast уведомлениями и минималистичным тёмным дизайном.
### Итого
- Количество промптов: 10
- Что пришлось исправлять вручную:"
1. Убрала дублирование _utcnow в enrollment.py, test.py, certificate.py
2. Исправила CASCADE vs RESTRICT в course.py
3. Заменила lazy="selectin" на lazy="select" в user.py
4. Перенесла _DUMMY_HASH на уровень модуля в auth.py
5. Удалила неиспользуемый JSONResponse в main.py (повторялось 4 раза)
6. Добавила pydantic[email] в requirements.txt
7. Понизила версию bcrypt до 4.0.1 (конфликт с passlib)
8. Убрала connect_args из async engine в database.py
9. Добавила selectinload для certificate.user и certificate.course
10. Добавила DbSession в database.py
11. Исправила логин во фронтенде: form-urlencoded → JSON"
- Время: ~360 мин
---