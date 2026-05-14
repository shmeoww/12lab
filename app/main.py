"""
app/main.py

Точка входа FastAPI-приложения.

Запуск для разработки:
    uvicorn app.main:app --reload

Запуск в продакшне:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_all_tables

from app.routers import auth, courses, lessons, enrollments, tests, certificates

# ── Импорт роутеров ───────────────────────────────────────────────────────────
# Раскомментируй по мере добавления модулей:
# from app.routers import users, courses, lessons, enrollments, auth

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер жизненного цикла приложения.
    Код до yield — startup, код после — shutdown.
    """
    # Startup
    logger.info("🚀 Запуск %s v%s", settings.app_name, settings.app_version)
    if settings.debug:
        # В dev-режиме создаём таблицы автоматически.
        # В продакшне используй: alembic upgrade head
        await create_all_tables()
        logger.warning("⚠️  Таблицы созданы через create_all (только для разработки)")

    yield  # Приложение работает

    # Shutdown
    logger.info("🛑 Остановка приложения")


# ── Создание экземпляра приложения ────────────────────────────────────────────
def create_application() -> FastAPI:
    """
    Фабричная функция — позволяет легко создавать тестовые экземпляры
    с разными настройками.
    """
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "REST API платформы онлайн-обучения. "
            "Документация: /docs (Swagger) или /redoc."
        ),
        docs_url="/docs" if settings.debug else None,   # Скрыть Swagger в проде
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(courses.router, prefix="/api/v1")
    application.include_router(lessons.router, prefix="/api/v1")
    application.include_router(enrollments.router, prefix="/api/v1")
    application.include_router(tests.router,       prefix="/api/v1")
    application.include_router(certificates.router, prefix="/api/v1")
    # ── Роутеры ───────────────────────────────────────────────────────────────
    # Подключай роутеры здесь по мере реализации:
    #
    # application.include_router(
    #     auth.router,
    #     prefix="/api/v1/auth",
    #     tags=["Auth"],
    # )
    # application.include_router(
    #     users.router,
    #     prefix="/api/v1/users",
    #     tags=["Users"],
    # )
    # application.include_router(
    #     courses.router,
    #     prefix="/api/v1/courses",
    #     tags=["Courses"],
    # )

    return application


app = create_application()


# ── Системные эндпоинты ───────────────────────────────────────────────────────
@app.get("/", tags=["System"], summary="Корневой эндпоинт")
async def root() -> dict[str, str]:
    return {"message": f"Добро пожаловать в {settings.app_name}!"}


@app.get("/health", tags=["System"], summary="Healthcheck для мониторинга")
async def health_check() -> dict[str, Any]:
    """
    Проверка работоспособности сервиса.
    Используется load-balancer'ами и системами мониторинга.
    """
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }
