# logging_handlers.py

import os
from logging.handlers import TimedRotatingFileHandler

class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, filename, log_dir='logs', when='midnight', interval=1, backupCount=7, encoding=None, delay=False, utc=False):
        self.log_dir = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        full_log_file = os.path.join(self.log_dir, filename)
        super(CustomTimedRotatingFileHandler, self).__init__(full_log_file, when, interval, backupCount, encoding, delay, utc)

    # Если требуется, можете переопределить метод doRollover()

    def getLogFileName(self, current_date):
        base_filename, file_extension = os.path.splitext(self.baseFilename)
        return f"{base_filename}_{current_date}.{file_extension}"
