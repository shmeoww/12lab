# Code Review — Задание 2

**ФИО:** Калинина Дарья Николаевна  
**Группа:** 220032-11  
**Вариант:** 7  
**Предметная область:** Платформа онлайн-обучения  

---

## Описание

В рамках Задания 1 весь код генерировался с помощью ИИ-инструментов.
В процессе code review было найдено и исправлено 11 проблем:
уязвимости, логические ошибки, проблемы производительности и несовместимости версий.

---

## Найденные и исправленные проблемы

---

### 1. Дублирование функции `_utcnow`

**Файлы:** `app/models/enrollment.py`, `app/models/test.py`, `app/models/certificate.py`

**Что сгенерировал ИИ:**
```python
# В каждом из трёх файлов была своя копия функции
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
```

**В чём проблема:**  
Нарушение принципа DRY (Don't Repeat Yourself). При необходимости изменить
логику получения времени пришлось бы менять её в трёх местах.
Функция уже была определена в `app/models/mixins.py`.

**Как исправила:**  
Удалила дублирующиеся определения, добавила импорт из mixins:
```python
from app.models.mixins import _utcnow
```

---

### 2. Противоречие `CASCADE` vs `RESTRICT` в модели курса

**Файл:** `app/models/course.py`

**Что сгенерировал ИИ:**
```python
# В user.py — cascade="all, delete-orphan" (SQLAlchemy удалит курсы)
owned_courses = relationship("Course", cascade="all, delete-orphan")

# В course.py — ondelete="RESTRICT" (БД запрещает удаление)
owner_id = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
```

**В чём проблема:**  
Прямое противоречие: SQLAlchemy говорит "удали связанные курсы при удалении
пользователя", а база данных говорит "запрещаю удалять пользователя у которого
есть курсы". При попытке удалить пользователя с курсами возникла бы ошибка.

**Как исправила:**
```python
owner_id = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
```

---

### 3. Избыточная загрузка связей `lazy="selectin"` в модели User

**Файл:** `app/models/user.py`

**Что сгенерировал ИИ:**
```python
owned_courses = relationship("Course", lazy="selectin")
enrollments = relationship("Enrollment", lazy="selectin")
tests = relationship("Test", lazy="selectin")
certificates = relationship("Certificate", lazy="selectin")
```

**В чём проблема:**  
`lazy="selectin"` означает что при каждой загрузке пользователя автоматически
подгружаются все его курсы, записи, тесты и сертификаты. Для пользователя
со сотнями записей это дорогостоящая операция даже когда эти данные не нужны
(например при проверке JWT токена).

**Как исправила:**
```python
owned_courses = relationship("Course", lazy="select")
enrollments = relationship("Enrollment", lazy="select")
tests = relationship("Test", lazy="select")
certificates = relationship("Certificate", lazy="select")
```

---

### 4. `_DUMMY_HASH` определён внутри функции

**Файл:** `app/routers/auth.py`

**Что сгенерировал ИИ:**
```python
async def login(...):
    # Пересоздаётся при каждом запросе
    _DUMMY_HASH = "$2b$12$KIXjJ9i5QnGD8Z6nZJFKwu..."
```

**В чём проблема:**  
Константа пересоздаётся при каждом HTTP запросе на логин.
Хотя накладные расходы минимальны, это нарушает принцип размещения
констант на уровне модуля.

**Как исправила:**  
Перенесла на уровень модуля, до определения роутера:
```python
# Фиктивный хэш для защиты от user enumeration attack
_DUMMY_HASH: str = "$2b$12$KIXjJ9i5QnGD8Z6nZJFKwu..."

router = APIRouter(...)
```

---

### 5. Неиспользуемый импорт `JSONResponse` (повторялся 4 раза)

**Файлы:** все версии `app/main.py` на протяжении разработки

**Что сгенерировал ИИ:**
```python
from fastapi.responses import JSONResponse  # нигде не используется
```

**В чём проблема:**  
Неиспользуемые импорты засоряют код и вводят читателя в заблуждение.
Это устойчивый паттерн конкретной модели — импорт добавлялся автоматически
в каждую новую версию `main.py` (4 раза за всю разработку).

**Как исправила:**  
Удалила строку импорта во всех файлах где она появлялась.

---

### 6. Отсутствующий пакет `pydantic[email]`

**Файл:** `requirements.txt`

**Что сгенерировал ИИ:**
pydantic==2.10.2

**В чём проблема:**  
Схема `UserCreate` использует тип `EmailStr` из Pydantic, который требует
дополнительного пакета `email-validator`. Без него сервер падал при старте
с ошибкой `ImportError: email-validator is not installed`.

**Как исправила:**
pydantic[email]==2.10.2
---

### 7. Конфликт версий `bcrypt` и `passlib`

**Файл:** `requirements.txt`

**Что сгенерировал ИИ:**
passlib[bcrypt]==1.7.4

bcrypt не был явно указан — устанавливалась последняя версия

**В чём проблема:**  
`passlib 1.7.4` несовместима с `bcrypt >= 4.1.0`. При попытке захэшировать
пароль возникала ошибка: AttributeError: module 'bcrypt' has no attribute 'about'

**Как исправила:**  
Явно зафиксировала совместимую версию:
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
---

### 8. Лишний `connect_args` в асинхронном движке SQLAlchemy

**Файл:** `app/database.py`

**Что сгенерировал ИИ:**
```python
engine = create_async_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # лишнее
)
```

**В чём проблема:**  
`check_same_thread=False` — параметр для синхронного SQLite драйвера.
Для асинхронного `aiosqlite` он не нужен, так как aiosqlite управляет
потоками самостоятельно. Параметр игнорируется но создаёт путаницу.

**Как исправила:**
```python
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    # connect_args убран — не нужен для aiosqlite
)
```

---

### 9. Обращение к связям без `selectinload` в async контексте

**Файл:** `app/routers/certificates.py`

**Что сгенерировал ИИ:**
```python
result = await db.execute(
    select(Certificate).where(
        Certificate.certificate_number == certificate_number
    )
)
# Дальше:
student_name = certificate.user.full_name  # обращение к связи
course_title = certificate.course.title    # обращение к связи
```

**В чём проблема:**  
Критическая ошибка. Наши модели используют `lazy="select"` (синхронная
ленивая загрузка). В async контексте обращение к незагруженной связи
вызывает `MissingGreenlet` и сервер возвращает `500 Internal Server Error`.

**Как исправила:**  
Явно загрузила связанные объекты через `selectinload`:
```python
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(Certificate)
    .options(
        selectinload(Certificate.user),
        selectinload(Certificate.course),
    )
    .where(Certificate.certificate_number == certificate_number)
)
```

---

### 10. `DbSession` не определён в `app/database.py`

**Файл:** `app/routers/analytics.py`

**Что сгенерировал ИИ:**
```python
from app.database import DbSession  # ImportError: cannot import name 'DbSession'
```

**В чём проблема:**  
Модуль `analytics.py` импортировал `DbSession` из `app/database.py`,
но там этот тип не был определён. В других роутерах `DbSession` определялся
локально в каждом файле — несогласованность стиля.

**Как исправила:**  
Добавила определение в `app/database.py` один раз для всего проекта:
```python
from typing import Annotated
from fastapi import Depends

DbSession = Annotated[AsyncSession, Depends(get_db)]
```

---

### 11. Неправильный формат запроса логина на фронтенде

**Файл:** `static/index.html`

**Что сгенерировал ИИ:**
```javascript
const res = await fetch(`${API}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({ username: email, password }),
});
```

**В чём проблема:**  
ИИ предположил что бэкенд использует OAuth2 Password Flow
(`application/x-www-form-urlencoded` с полем `username`).
Но наш эндпоинт `/auth/login` принимает JSON с полем `email`.
Логин всегда возвращал `422 Unprocessable Entity`.

**Как исправила:**
```javascript
const res = await fetch(`${API}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password }),
});
```
### 12. Невалидный `_DUMMY_HASH` в auth.py

**Что сгенерировал ИИ:**
_DUMMY_HASH содержал выдуманную строку не являющуюся настоящим bcrypt хэшем.

**В чём проблема:**
При логине с несуществующим email passlib пытается верифицировать пароль
против этого хэша и падает с ValueError вместо возврата 401.
Обнаружено тестом test_login_nonexistent_email.

**Как исправила:**
_DUMMY_HASH: str = hash_password("dummy_for_timing_attack_prevention")

---

## Итого

| # | Файл | Тип проблемы | Критичность |
|---|---|---|---|
| 1 | models/enrollment.py и др. | Дублирование кода | Низкая |
| 2 | models/course.py | Логическая ошибка | Высокая |
| 3 | models/user.py | Производительность | Средняя |
| 4 | routers/auth.py | Стиль кода | Низкая |
| 5 | main.py | Неиспользуемый импорт | Низкая |
| 6 | requirements.txt | Отсутствующая зависимость | Высокая |
| 7 | requirements.txt | Конфликт версий | Высокая |
| 8 | database.py | Лишний параметр | Низкая |
| 9 | routers/certificates.py | Критическая ошибка (500) | Критическая |
| 10 | routers/analytics.py | Ошибка импорта | Высокая |
| 11 | static/index.html | Логическая ошибка | Высокая |

**Найдено проблем:** 11  
**Исправлено:** 11  
**Критических:** 1 (проблема №9 — `MissingGreenlet` в сертификатах)  
**Устойчивых паттернов ИИ:** 1 (неиспользуемый `JSONResponse` — повторялся 4 раза)