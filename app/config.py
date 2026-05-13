"""
app/config.py

Централизованная конфигурация через pydantic-settings.
Значения читаются из .env файла автоматически.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Приложение
    app_name: str = "Learning Platform"
    app_version: str = "0.1.0"
    debug: bool = True

    # База данных
    database_url: str = "sqlite+aiosqlite:///./learning_platform.db"

    # JWT
    secret_key: str = "CHANGE_ME"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # Пагинация
    default_page_size: int = 20
    max_page_size: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def get_allowed_origins(self) -> list[str]:
        """Парсит строку с origins в список."""
        return [o.strip() for o in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """
    Кэшированный singleton настроек.
    lru_cache гарантирует что .env читается один раз.
    """
    return Settings()