"""
Telegram Disappearing Media Saver

Сохраняет исчезающие медиафайлы (фото, видео, документы) из чатов Telegram.
Поддерживает локальное сохранение и S3-совместимые хранилища.
"""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Union, Any

from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    TypeMessageMedia
)
from telethon.tl.custom import Message

from config import settings
from logger import setup_logger
from storage import get_storage, MediaStorage

# Инициализация логгера и хранилища
logger = setup_logger(__name__)
storage: MediaStorage = get_storage()

# Создание клиента Telegram
client = TelegramClient(
    'tg_session',           # Имя файла сессии
    settings.api_id,
    settings.api_hash
)

# --- Вспомогательные функции ---

def sanitize_filename(text: str, max_length: int = 50) -> str:
    """
    Очищает строку для использования в имени файла.
    
    Args:
        text: Исходная строка
        max_length: Максимальная длина результата
        
    Returns:
        Очищенная строка, безопасная для использования в имени файла
    """
    # Заменяем недопустимые символы на подчеркивания
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        text = text.replace(char, '_')
    
    # Ограничиваем длину
    if len(text) > max_length:
        text = text[:max_length]
    
    return text


async def get_chat_identifier(event: events.NewMessage) -> str:
    """
    Получает читаемый идентификатор чата.
    
    Args:
        event: Событие нового сообщения
        
    Returns:
        Строковый идентификатор чата (название, username или ID)
    """
    chat = await event.get_chat()
    identifier = getattr(chat, 'title', None) or getattr(chat, 'username', None)
    return sanitize_filename(identifier or str(chat.id))


async def get_sender_name(event: events.NewMessage) -> str:
    """
    Получает имя отправителя сообщения.
    
    Args:
        event: Событие нового сообщения
        
    Returns:
        Имя отправителя
    """
    sender = await event.get_sender()
    name = getattr(sender, 'username', None) or getattr(sender, 'first_name', None)
    return sanitize_filename(name or str(sender.id))


def generate_filename(
    timestamp: datetime,
    chat_identifier: str,
    sender_name: str,
    extension: str
) -> Path:
    """
    Генерирует имя файла для сохраняемого медиа.
    
    Args:
        timestamp: Время получения сообщения
        chat_identifier: Идентификатор чата
        sender_name: Имя отправителя
        extension: Расширение файла (включая точку, например '.jpg')
        
    Returns:
        Path объект с сгенерированным именем файла
    """
    time_str = timestamp.strftime("%Y%m%d_%H%M%S")
    filename = f"{time_str}_{chat_identifier}_{sender_name}{extension}"
    return Path(filename)


async def download_media_content(message: Message) -> Optional[bytes]:
    """
    Скачивает медиа-контент из сообщения.
    
    Args:
        message: Объект сообщения Telethon
        
    Returns:
        Байтовое содержимое файла или None при ошибке
    """
    try:
        content = await client.download_media(message, bytes)
        return content
    except Exception as e:
        logger.error(f"Ошибка при скачивании медиа: {e}")
        return None


async def process_media_message(event: events.NewMessage) -> None:
    """
    Обрабатывает сообщение с медиа-файлом.
    
    Args:
        event: Событие нового сообщения
    """
    message: Message = event.message
    
    # Проверяем, есть ли медиа в сообщении
    if not hasattr(message, 'media') or not message.media:
        return
    
    # Логируем информацию о TTL (самоуничтожении)
    ttl = getattr(message, 'ttl_seconds', None)
    if ttl:
        logger.info(f"Обнаружено самоуничтожающееся сообщение! TTL: {ttl} секунд")
    
    # Получаем информацию о чате и отправителе
    chat_identifier = await get_chat_identifier(event)
    sender_name = await get_sender_name(event)
    timestamp = datetime.now()
    
    logger.info(f"Обработка медиа от {sender_name} в чате {chat_identifier}")
    
    # Определяем тип медиа и расширение файла
    media: TypeMessageMedia = message.media
    extension: str = ''
    
    if isinstance(media, MessageMediaPhoto):
        extension = '.jpg'
        logger.info("Тип медиа: Фото")
    elif isinstance(media, MessageMediaDocument):
        extension = '.bin'  # Временное расширение, будет заменено
        logger.info("Тип медиа: Документ/Видео")
        # Пытаемся определить реальное расширение из атрибутов документа
        if hasattr(media.document, 'mime_type'):
            mime_type = media.document.mime_type
            if mime_type:
                ext_map = {
                    'video/mp4': '.mp4',
                    'video/x-matroska': '.mkv',
                    'image/gif': '.gif',
                    'application/pdf': '.pdf',
                    'text/plain': '.txt',
                    'application/zip': '.zip'
                }
                extension = ext_map.get(mime_type, '.bin')
                logger.info(f"MIME-тип: {mime_type}, расширение: {extension}")
    else:
        logger.warning(f"Неизвестный тип медиа: {type(media)}")
        return
    
    # Скачиваем содержимое
    file_content = await download_media_content(message)
    if not file_content:
        logger.error("Не удалось скачать медиа-контент")
        return
    
    # Генерируем имя файла
    filename = generate_filename(timestamp, chat_identifier, sender_name, extension)
    
    # Сохраняем через выбранное хранилище
    try:
        saved_path = await storage.save(filename, file_content)
        logger.info(f"✅ Медиа успешно сохранено: {saved_path}")
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении медиа: {e}")


@client.on(events.NewMessage)
async def handle_new_message(event: events.NewMessage) -> None:
    """
    Главный обработчик новых сообщений.
    
    Args:
        event: Событие нового сообщения
    """
    # Фильтруем сообщения по целевому чату (если указан)
    if settings.target_chat and event.chat_id != settings.target_chat:
        # Проверяем возможность передачи username
        if isinstance(settings.target_chat, str) and not settings.target_chat.startswith('-'):
            try:
                entity = await client.get_entity(settings.target_chat)
                if event.chat_id == entity.id:
                    pass  # Это целевой чат
                else:
                    return
            except:
                return
        else:
            return
    
    logger.debug(f"Получено сообщение из чата {event.chat_id}")
    await process_media_message(event)


async def main() -> None:
    """
    Главная асинхронная функция запуска клиента.
    """
    logger.info("=" * 60)
    logger.info("Запуск Telegram Disappearing Media Saver")
    logger.info(f"Конфигурация:")
    logger.info(f"  - API ID: {settings.api_id}")
    logger.info(f"  - Номер телефона: {settings.phone_number}")
    logger.info(f"  - Целевой чат: {settings.target_chat or 'Все чаты'}")
    logger.info(f"  - Хранилище: {'S3' if settings.s3.use_s3 else 'Локальное'}")
    if settings.s3.use_s3:
        logger.info(f"    - S3 Endpoint: {settings.s3.endpoint_url}")
        logger.info(f"    - S3 Bucket: {settings.s3.bucket_name}")
    else:
        logger.info(f"    - Папка сохранения: {settings.save_folder}")
    logger.info("=" * 60)
    
    try:
        await client.start(phone=settings.phone_number)
        logger.info("Клиент успешно авторизован")
        
        # Выводим информацию о текущем пользователе
        me = await client.get_me()
        logger.info(f"Запущено от имени: {me.first_name} (@{me.username})")
        
        # Запускаем бесконечный цикл прослушивания
        logger.info("Начинаем прослушивание сообщений...")
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        logger.info("Клиент остановлен")


def start():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")
        raise

if __name__ == '__main__':
    start()