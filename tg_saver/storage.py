import os
from abc import ABC, abstractmethod
from pathlib import Path
import boto3
from botocore.client import Config
from .config import settings
from .logger import setup_logger

logger = setup_logger()

class MediaStorage(ABC):
    """Абстрактный класс для сохранения медиа."""
    
    @abstractmethod
    async def save(self, file_path: Path, content: bytes) -> str:
        """Сохраняет файл и возвращает путь или идентификатор."""
        pass

class LocalStorage(MediaStorage):
    """Сохраняет файлы локально."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    async def save(self, file_path: Path, content: bytes) -> str:
        full_path = self.base_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        logger.info(f"Файл сохранён локально: {full_path}")
        return str(full_path)

class S3Storage(MediaStorage):
    """Сохраняет файлы в S3-совместимое хранилище."""
    
    def __init__(self):
        s3_settings = settings.s3
        self.client = boto3.client(
            's3',
            endpoint_url=s3_settings.endpoint_url,
            aws_access_key_id=s3_settings.access_key,
            aws_secret_access_key=s3_settings.secret_key,
            region_name=s3_settings.region_name,
            config=Config(signature_version='s3v4')
        )
        self.bucket = s3_settings.bucket_name
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Проверяет существование бакета и создаёт его при необходимости."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)
            logger.info(f"Бакет {self.bucket} создан.")
    
    async def save(self, file_path: Path, content: bytes) -> str:
        # Преобразуем путь к файлу в строку для использования в качестве ключа
        key = str(file_path)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        # Генерируем публичную ссылку (если бакет публичный)
        public_url = f"{settings.s3.endpoint_url}/{self.bucket}/{key}"
        logger.info(f"Файл сохранён в S3: {public_url}")
        return public_url

def get_storage() -> MediaStorage:
    """Фабрика для получения нужного хранилища на основе конфигурации."""
    if settings.s3.use_s3:
        return S3Storage()
    else:
        return LocalStorage(settings.save_folder)