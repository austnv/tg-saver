import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from config import settings

def setup_logger(name: str = "tg-saver") -> logging.Logger:
    """Настраивает и возвращает логгер с ротацией файлов."""
    # Создаём директорию для логов, если её нет
    log_dir = settings.log.log_dir
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Форматтер для всех обработчиков
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # --- Обработчик для файла с ротацией ---
    # Используем базовое имя файла (без суффикса)
    base_log_path = log_dir / "app.log"
    file_handler = TimedRotatingFileHandler(
        filename=str(base_log_path),
        when=settings.log.rotation_time,
        interval=1,
        backupCount=settings.log.max_files,
        encoding='utf-8'
    )
    file_handler.suffix = "%Y-%m-%d"
    # Переопределяем функцию формирования имени файла для формата app.YYYY-MM-DD.log
    file_handler.namer = lambda name: name.replace(".log.", ".").replace("..", ".")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # --- Обработчик для вывода в консоль (опционально) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger