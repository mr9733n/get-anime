# logging_handlers.py

import os
import logging
from logging.handlers import TimedRotatingFileHandler

class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename, when='midnight', interval=1, maxBytes=10485760, backupCount=5, encoding=None, delay=False, utc=False, atTime=None):
        self.maxBytes = maxBytes
        self.log_dir = 'logs'
        os.makedirs(self.log_dir, exist_ok=True)
        full_log_file = os.path.join(self.log_dir, filename)
        super(CustomTimedRotatingFileHandler, self).__init__(full_log_file, when, interval, backupCount, encoding, delay, utc, atTime)

    def getLogFileName(self, current_date):
        base_filename, file_extension = os.path.splitext(self.baseFilename)
        return f"{base_filename}_{current_date}.{file_extension}"

    def shouldRollover(self, record):
        """
        Определяет, нужно ли делать ротацию: если истёк интервал по времени или размер файла превышен.
        """
        # Сначала проверим условие таймовой ротации
        time_based = super().shouldRollover(record)

        # Если файл ещё не существует, то нет смысла проверять его размер
        if not os.path.exists(self.baseFilename):
            size_based = False
        else:
            # Получаем размер файла
            size = os.stat(self.baseFilename).st_size
            size_based = size >= self.maxBytes

        return time_based or size_based