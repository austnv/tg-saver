from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

class S3Settings(BaseSettings):
    """Настройки S3-совместимого хранилища."""
    use_s3: bool = False
    endpoint_url: str = ""
    access_key: str = ""
    secret_key: str = ""
    bucket_name: str = "tg-media"
    region_name: str = "us-east-1"

    class Config:
        env_prefix = "S3_"

class LogSettings(BaseSettings):
    """Настройки ротации логов."""
    log_dir: Path = Path("logs")
    max_files: int = 7
    rotation_time: str = "midnight"

    class Config:
        env_prefix = "LOG_"

class Settings(BaseSettings):
    """Главный класс конфигурации."""
    # Telegram
    api_id: int
    api_hash: str
    phone_number: str
    target_chat: Optional[str] = None
    
    # Локальное сохранение
    save_folder: Path = Path("saved_media")
    
    # Вложенные настройки
    s3: S3Settings = S3Settings()
    log: LogSettings = LogSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Инициализация настроек
settings = Settings()