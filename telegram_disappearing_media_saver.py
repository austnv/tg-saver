from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import os
import asyncio
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация - ЗАПОЛНИТЕ СВОИМИ ДАННЫМИ
API_ID = PASTE  # Замените на ваш API ID с my.telegram.org
API_HASH = 'PASTE'  # Замените на ваш API Hash с my.telegram.org
PHONE_NUMBER = '+PASTE'  # Замените на ваш номер телефона

# Настройки сохранения
SAVE_FOLDER = 'saved_media'
TARGET_CHAT = Nonde  # None для всех чатов, или укажите имя пользователя/ID чата для отслеживания конкретного чата

# Создаем папку для сохранения, если не существует
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

# Инициализация клиента
client = TelegramClient('disappearing_media_session', API_ID, API_HASH)

@client.on(events.NewMessage)
async def handle_new_message(event):
    """Обрабатывает новые сообщения для сохранения исчезающих медиафайлов."""
    message = event.message
    
    # Если указан конкретный чат и это сообщение не из него - игнорируем
    if TARGET_CHAT and event.chat_id != TARGET_CHAT:
        return
    
    logger.info(f"Получено сообщение из чата {event.chat_id}")
    
    # Проверяем, есть ли медиа в сообщении (даже без ttl_seconds)
    if hasattr(message, 'media') and message.media:
        logger.info(f"Сообщение содержит медиа: {type(message.media)}")
        
        # Проверяем наличие ttl_seconds
        ttl = getattr(message, 'ttl_seconds', None)
        if ttl:
            logger.info(f"Это самоуничтожающееся сообщение! TTL: {ttl} секунд")
        
        chat = await event.get_chat()
        sender = await event.get_sender()
        chat_title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(chat.id)
        sender_name = getattr(sender, 'username', None) or getattr(sender, 'first_name', None) or str(sender.id)
        
        logger.info(f"Обнаружено медиа от {sender_name} в чате {chat_title}")
        
        # Создаем имя файла с информацией о сообщении
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{timestamp}_{chat_title}_{sender_name}"
        
        # Сохраняем медиафайл независимо от ttl_seconds (сохраняем все медиа)
        if isinstance(message.media, MessageMediaPhoto):
            filename = f"{base_filename}.jpg"
            path = os.path.join(SAVE_FOLDER, filename)
            
            await client.download_media(message, path)
            logger.info(f"Фото сохранено как {path}")
            
        elif isinstance(message.media, MessageMediaDocument):
            # Для видео и других документов
            filename = f"{base_filename}"  # Расширение будет добавлено автоматически
            path = os.path.join(SAVE_FOLDER, filename)
            
            await client.download_media(message, path)
            logger.info(f"Документ/видео сохранен как {path}")
        
        else:
            logger.warning(f"Неизвестный тип медиа: {type(message.media)}")

async def main():
    """Основная функция для запуска клиента."""
    # Запускаем клиент и входим в аккаунт
    await client.start(phone=PHONE_NUMBER)
    
    # Проверяем авторизацию
    if not await client.is_user_authorized():
        logger.info("Требуется авторизация...")
        
        # Запрашиваем код подтверждения
        await client.send_code_request(PHONE_NUMBER)
        code = input('Введите код подтверждения: ')
        await client.sign_in(PHONE_NUMBER, code)
    
    me = await client.get_me()
    logger.info(f"Авторизация успешна: {me.username or me.first_name}")
    
    logger.info("Начинаю мониторинг исчезающих медиафайлов...")
    
    # Дополнительный код для получения последних сообщений из целевого чата
    logger.info(f"Пытаюсь получить последние сообщения из чата {TARGET_CHAT}...")
    async for message in client.iter_messages(TARGET_CHAT, limit=50):
        if hasattr(message, 'media') and message.media:
            logger.info(f"Найдено медиа сообщение, сохраняем...")
            
            # Создаем имя файла 
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_existing_media"
            path = os.path.join(SAVE_FOLDER, filename)
            
            await client.download_media(message, path)
            logger.info(f"Существующее медиа сохранено как {path}")
    
    # Продолжаем работу, пока клиент запущен
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main()) 