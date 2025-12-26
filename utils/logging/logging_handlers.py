# logging_handlers.py
import os
import datetime
import time

from logging.handlers import TimedRotatingFileHandler


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename, when='midnight', interval=1, maxBytes=10485760, backupCount=5, encoding=None, delay=False, utc=False, atTime=None):
        self.maxBytes = maxBytes
        self.log_dir = 'logs'
        os.makedirs(self.log_dir, exist_ok=True)
        full_log_file = os.path.join(self.log_dir, filename)
        super(CustomTimedRotatingFileHandler, self).__init__(full_log_file, when, interval, backupCount, encoding, delay, utc, atTime)

    def getLogFileName(self, current_time):
        """Генерирует имя файла с учетом полного временного штампа."""
        base_filename, file_extension = os.path.splitext(self.baseFilename)
        # Форматируем дату и время: год-месяц-день_часы-минуты-секунды
        timestamp = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        return f"{base_filename}_{timestamp}{file_extension}"

    def shouldRollover(self, record):
        """
        Определяет, нужно ли выполнять ротацию: если истек интервал по времени или размер файла превышен.
        """
        # Проверяем условие таймовой ротации
        time_based = super().shouldRollover(record)

        # Если файла ещё нет, то размер проверить не имеет смысла
        if not os.path.exists(self.baseFilename):
            size_based = False
        else:
            # Получаем размер файла
            size = os.stat(self.baseFilename).st_size
            size_based = size >= self.maxBytes

        return time_based or size_based

    def doRollover(self):
        """
        Переопределяем метод ротации, чтобы использовать наше имя файла с полным временным штампом.
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        current_time = datetime.datetime.now()
        dfn = self.getLogFileName(current_time)
        # Если по какой-то причине такой файл уже существует, удаляем его
        if os.path.exists(dfn):
            os.remove(dfn)
        self.rotate(self.baseFilename, dfn)
        # Удаляем старые файлы, если число резервных файлов превышает backupCount
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)
        self.mode = "a"
        self.stream = self._open()

        # Обновляем время следующего rollover

        current_time_sec = time.time()
        new_rollover_at = self.computeRollover(current_time_sec)
        # Если по какой-то причине новое время меньше текущего, корректируем
        while new_rollover_at <= current_time_sec:
            new_rollover_at += self.interval
        self.rolloverAt = new_rollover_at
