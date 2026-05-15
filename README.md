# Лабораторная работа №12

**ФИО:** Калинина Дарья Николаевна  
**Группа:** 220032-11  
**Вариант:** 7
**Предметная область:** Платформа онлайн-обучения  

---

## Выполненные задания
- **Задание 1, повышенная сложность** - Создание полноценного веб-приложения
- **Задание 2, повышенная сложность** - Code review сгенерированного кода
- **Задание 4, повышенная сложность** - Интеграция ИИ в CI/CD
- **Задание 7, повышенная сложность** - Генерация unit-тестов с высоким покрытием
---
## 📋 Описание проекта

**LearnFlow** — REST API для платформы онлайн-обучения, реализованное на FastAPI с асинхронной работой с базой данных. Система поддерживает полный цикл обучения: от регистрации пользователя до выдачи сертификата о прохождении курса.

### Основные сущности

| Сущность | Описание |
|---|---|
| `User` | Пользователь системы (студент или администратор) |
| `Course` | Учебный курс с названием и описанием |
| `Lesson` | Урок внутри курса (текст, видео, материалы) |
| `Enrollment` | Запись студента на курс с отслеживанием прогресса |
| `Test` | Тест к уроку с баллами и результатами |
| `Certificate` | Сертификат о завершении курса |

---

## 🛠 Стек технологий

| Категория | Технология |
|---|---|
| **Веб-фреймворк** | [FastAPI](https://fastapi.tiangolo.com/) |
| **ORM** | [SQLAlchemy 2.x](https://docs.sqlalchemy.org/) (async + AsyncSession) |
| **База данных** | SQLite (через `aiosqlite`) |
| **Миграции** | [Alembic](https://alembic.sqlalchemy.org/) |
| **Аутентификация** | JWT (python-jose) + bcrypt |
| **Валидация** | [Pydantic v2](https://docs.pydantic.dev/) |
| **Контейнеризация** | [Docker](https://www.docker.com/) + Docker Compose |
| **Тестирование** | pytest + httpx + pytest-asyncio |
| **Фронтенд** | Vanilla JS / CSS (SPA, один HTML-файл) |

### Создание администратора

Все пользователи по умолчанию регистрируются как студенты.
Чтобы назначить администратора, запусти скрипт:

```bash
python make_admin.py
```

Укажи email нужного пользователя внутри скрипта перед запуском.

---
## 🚀 Установка и запуск

### 1. Клонирование репозитория

```bash
git clone https://github.com/shmeoww/12lab
cd lab_12
```

### 2. Настройка переменных окружения

Скопируйте шаблон и заполните значения:

```bash
cp .env.example .env
```

Содержимое `.env.example` и пояснения:

```dotenv
# Секретный ключ для подписи JWT-токенов (любая случайная строка, мин. 32 символа)
SECRET_KEY=your-super-secret-key-change-me

# Алгоритм подписи JWT (рекомендуется HS256)
ALGORITHM=HS256

# Время жизни access-токена в минутах
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Время жизни refresh-токена в днях
REFRESH_TOKEN_EXPIRE_DAYS=7

# URL подключения к базе данных
# SQLite (по умолчанию):
DATABASE_URL=sqlite+aiosqlite:///./learning.db
# PostgreSQL (для продакшена):
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/learning_db
```

### 3. Виртуальное окружение и зависимости

```bash
# Создание окружения
python -m venv venv

# Активация (Linux / macOS)
source venv/bin/activate

# Активация (Windows)
venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt
```

### 4. Применение миграций

```bash
> В dev-режиме таблицы создаются автоматически при запуске.
```

### 5. Запуск сервера

```bash
uvicorn app.main:app --reload
```

| Интерфейс | URL |
|---|---|
| 🖥 Фронтенд (SPA) | http://127.0.0.1:8000/app |
| 📖 Swagger UI | http://127.0.0.1:8000/docs |
| 📄 ReDoc | http://127.0.0.1:8000/redoc |

### 6. Запуск через Docker

```bash
# Собрать и запустить
docker-compose up --build

# В фоне
docker-compose up -d --build

# Остановить
docker-compose down
```

---

## 📡 API Эндпоинты

### 🔐 Auth — `/api/v1/auth`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `POST` | `/auth/register` | Регистрация нового пользователя | Публичный |
| `POST` | `/auth/login` | Вход (возвращает `access_token` + `refresh_token`) | Публичный |
| `POST` | `/auth/refresh` | Обновление токена по `refresh_token` | Публичный |

---

### 📚 Courses — `/api/v1/courses`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `GET` | `/courses/` | Получить список всех курсов | Авторизованный |
| `GET` | `/courses/{id}` | Получить курс по ID | Авторизованный |
| `POST` | `/courses/` | Создать новый курс | 🔴 Админ |
| `PUT` | `/courses/{id}` | Обновить курс | 🔴 Админ |
| `DELETE` | `/courses/{id}` | Удалить курс | 🔴 Админ |

---

### 📖 Lessons — `/api/v1/lessons`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `GET` | `/courses/{course_id}/lessons/` | Получить все уроки (фильтр по `course_id`) | Авторизованный |
| `GET` | `/courses/{course_id}/lessons/{id}` | Получить урок по ID | Авторизованный |
| `POST` | `/courses/{course_id}/lessons/` | Создать урок | 🔴 Админ |
| `PUT` | `/courses/{course_id}/lessons/{id}` | Обновить урок | 🔴 Админ |
| `DELETE` | `/courses/{course_id}/lessons/{id}` | Удалить урок | 🔴 Админ |

---

### 🎓 Enrollments — `/api/v1/enrollments`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `GET` | `/enrollments/my` | Список курсов текущего студента | 🟢 Студент |
| `POST` | `/enrollments/{course_id}` | Записаться на курс | 🟢 Студент |
| `DELETE` | `/enrollments/{course_id}` | Отписаться от курса | 🟢 Студент |

---

### ✅ Tests — `/api/v1/tests`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `POST` | `/courses/{course_id}/tests/` | Сдать тест по уроку (передать ответы, получить балл) | 🟢 Студент |
| `GET` | `/courses/{course_id}/tests/my` | Мои результаты тестов | 🟢 Студент |

---

### 🏆 Certificates — `/api/v1/certificates`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `GET` | `/certificates/my` | Мои сертификаты | 🟢 Студент |
| `GET` | `/certificates/{certificate_number}` | Получить сертификат по ID | Публичный |
| `POST` | `/certificates/{course_id}` | Выдать сертификат | 🟢 Студент (сам запрашивает) |

---

### 📊 Analytics — `/api/v1/analytics`

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `GET` | `/analytics/stats` | Общая статистика платформы | 🔴 Админ |
| `GET` | `/analytics/top-courses` | Топ-5 курсов по записям | 🔴 Админ |
| `GET` | `/analytics/my-stats` | Личная статистика студента | 🟢 Студент |

---

### ⚙️ System

| Метод | Путь | Описание | Доступ |
|---|---|---|---|
| `GET` | `/` | Информация об API (версия, статус) | Публичный |
| `GET` | `/health` | Health-check (для Docker / мониторинга) | Публичный |
| `GET` | `/app` | Отдаёт фронтенд SPA (`static/index.html`) | Публичный |

---

## 🔒 Права доступа

### Студент 🟢

- Просмотр списка курсов и уроков
- Запись/отписка от курсов
- Сдача тестов и просмотр своих результатов
- Просмотр своих сертификатов
- Просмотр личной статистики (`/analytics/my-stats`)

### Администратор 🔴

Всё то же, что студент, **плюс:**

- Создание, редактирование и удаление курсов и уроков
- Просмотр всех записей на курсы
- Выдача сертификатов студентам
- Доступ к общей статистике платформы (`/analytics/stats`, `/analytics/top-courses`)


---

## 🧪 Примеры запросов (curl)

### Регистрация нового пользователя

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@example.com",
    "password": "securepassword",
    "full_name": "Иван Иванов"
  }'
```

**Ответ:**
```json
{
  "id": 2,
  "email": "student@example.com",
  "full_name": "Иван Иванов",
  "is_admin": false,
  "created_at": "2024-01-15T10:30:00"
}
```

---

### Вход в систему

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"email": "...", "password": "..."}'
```

**Ответ:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

### Использование токена в запросах

```bash
# Сохранить токен в переменную
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Получить список курсов
curl http://127.0.0.1:8000/api/v1/courses/ \
  -H "Authorization: Bearer $TOKEN"

# Записаться на курс с ID=1
curl -X POST http://127.0.0.1:8000/api/v1/enrollments/1 \
  -H "Authorization: Bearer $TOKEN"

# Моя статистика
curl http://127.0.0.1:8000/api/v1/analytics/my-stats \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🧪 Запуск тестов

```bash
# Все тесты с подробным выводом
pytest tests/ -v

# Конкретный модуль
pytest tests/test_auth.py -v

# С покрытием
pytest tests/ -v --cov=app --cov-report=term-missing

# Только быстрые тесты (без интеграционных)
pytest tests/ -v -m "not slow"
```

---
## **Задание 2, повышенная сложность** — Code review сгенерированного кода.
Это задание находится в REVIEW.md
---

## **Задание 4, повышенная сложность** CI/CD — Автоматическое AI ревью

При создании Pull Request автоматически запускается GitHub Actions workflow,
который анализирует изменения кода с помощью Mistral 7B (Hugging Face)
и публикует комментарий прямо в PR.

### Как это работает

1. Разработчик создаёт Pull Request
2. GitHub Actions запускает `.github/workflows/ai-review.yml`
3. Скрипт `.github/scripts/ai_review.py` получает diff изменений
4. Diff отправляется в Hugging Face API (Mistral-7B-Instruct)
5. AI пишет ревью в PR — описание изменений, сильные стороны, проблемы, оценку

### Структура workflow
.github/
├── workflows/
│   └── ai-review.yml    # триггер на PR, запуск скрипта
└── scripts/
└── ai_review.py     # получение diff + запрос к HF API + комментарий в PR

### Настройка

Добавь в GitHub репозитории: Settings → Secrets → Actions:

| Secret | Описание |
|---|---|
| `HF_API_KEY` | API ключ с huggingface.co |

### Пример результата

![AI Code Review в PR](docs/ai-review-action.jpg)

---

## 📝 Лицензия

Учебный проект. Все права принадлежат автору.

---

<div align="center">
  <sub>Калинина Дарья Николаевна · Группа 220032-11 · Вариант 7</sub>
</div>


4 задание
1 шаг
git remote add origin https://github.com/shmeoww/12lab
git branch -M main
git push -u origin main

2 шаг
huggingface.co
регистрация там
API Keys, потом Create new secret key
копируем

3 шаг
открываю репозиторий на гитхаб
settings -> secret and variables -> Actions -> New repository secret

имя: HF_API_KEY
в secret встевляем сгенерированный ключ
Add secret

4 шаг 
создаем файлы workflow
в корне создаем папку .github и внутри нее
workflows/ai-review.yml
scripts/ai_review.py

их содержание
workflows/ai-review.yml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install requests

      - name: Run AI Review
        env:
          HF_API_KEY: ${{ secrets.HF_API_KEY }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: python .github/scripts/ai_review.py

scripts/ai_review.py
import os
import subprocess
import requests

# ── Получаем diff PR ────────────────────────────────────────────────────
base_sha = os.environ["BASE_SHA"]
head_sha = os.environ["HEAD_SHA"]

result = subprocess.run(
    ["git", "diff", f"{base_sha}...{head_sha}", "--stat"],
    capture_output=True, text=True
)
diff_stat = result.stdout[:500]

result2 = subprocess.run(
    ["git", "diff", f"{base_sha}...{head_sha}"],
    capture_output=True, text=True
)
diff_full = result2.stdout[:15000]

# ── Запрос к Hugging Face ───────────────────────────────────────────────
hf_token = os.environ["HF_API_KEY"]

prompt = f"""You are an experienced Python developer. Review this Pull Request.

CHANGED FILES STAT:
{diff_stat}

DIFF:
{diff_full}

Write a code review in Markdown with these sections:
1. **📝 Description** — what was changed (2-4 sentences)
2. **✅ What is good** — list of strengths
3. **⚠️ Potential issues** — bugs, vulnerabilities, bad practices
4. **💡 Suggestions** — concrete recommendations
5. **🔢 Score** — from 1 to 10 with brief explanation"""

response = requests.post(
    "https://router.huggingface.co/hf-inference/models/mistralai/Mistral-7B-Instruct-v0.3/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    },
    json={
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.7,
    },
    timeout=60,
)

if response.status_code != 200:
    print(f"❌ HF API error: {response.status_code} — {response.text}")
    exit(1)

data = response.json()
review_text = data["choices"][0]["message"]["content"]

# ── Публикуем комментарий в PR ──────────────────────────────────────────
comment_body = f"""## 🤖 AI Code Review (Mistral 7B)

{review_text}

---
<sub>Автоматическое ревью · коммит {head_sha[:7]}</sub>"""

repo = os.environ["REPO"]
pr_number = os.environ["PR_NUMBER"]
gh_token = os.environ["GH_TOKEN"]

resp = requests.post(
    f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
    headers={
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
    },
    json={"body": comment_body},
)

if resp.status_code == 201:
    print("✅ Комментарий успешно опубликован")
else:
    print(f"❌ Ошибка: {resp.status_code} — {resp.text}")
    exit(1)

5 шаг запушить на гитхаб
Шаг 5 — Запушить на GitHub
bash
git add .github/
git commit -m "add AI code review workflow"
git push origin main

Шаг 6 — Создать тестовую ветку и PR
bash
git checkout -b feature/test-ai-review
echo "# Test" >> TEST_NOTE.md
git add TEST_NOTE.md
git commit -m "test: trigger AI review"
git push origin feature/test-ai-review

Затем на GitHub:
Появится жёлтая плашка "Compare & pull request" — нажми её
Create pull request

Шаг 7 — Дождаться результата

Открой вкладку Actions в репозитории — увидишь запущенный workflow
Через 30–60 секунд вернись во вкладку Conversation в PR
Там будет комментарий от бота — делай скриншот

git checkout main
git add .github/
git commit -m "fix: update HF API endpoint"
git push origin main

git checkout feature/test-ai-review
echo "fix" >> TEST_NOTE.md
git add TEST_NOTE.md
git commit -m "test: retry after endpoint fix"
git push origin feature/test-ai-review