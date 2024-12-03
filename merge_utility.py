import asyncio
import logging
import time

import aiohttp
import requests
import qrcode
import os
import argparse
from qrcode.main import QRCode
from qrcode.image.pil import PilImage
import shutil
from tqdm import tqdm

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.tables import Base, Title, Episode, History, Franchise, FranchiseRelease, Poster, Schedule, Rating, Torrent, \
    ProductionStudio


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DatabaseMergeUtility")

MAIL_API_URL = f"https://api.postmarkapp.com/email"
TEMP_CLOUD_API = 'https://file.io'

TEMP_DB_NAME = 'temp_downloaded.db'
MERGED_DB_NAME = 'merged_database.db'
DB_NAME = 'anime_player.db'
QRCODE_NAME = 'qrcode.png'

class DatabaseMergeUtility:
    def __init__(self, db_path_1, db_path_2):
        # Подключение к двум базам данных
        self.engine_1 = create_engine(f'sqlite:///{db_path_1}', echo=False)
        self.engine_2 = create_engine(f'sqlite:///{db_path_2}', echo=False)

        # Сессии для работы с базами данных
        self.Session1 = sessionmaker(bind=self.engine_1)
        self.Session2 = sessionmaker(bind=self.engine_2)

    def get_all_data(self, session, model):
        try:
            return session.query(model).all()
        except Exception as e:
            logger.error(f"Ошибка при получении данных из модели {model.__tablename__}: {e}")
            return []

    def compare_databases(self):
        models = [Title, Episode, History, Franchise, FranchiseRelease, Poster, Schedule, Rating, Torrent,
                  ProductionStudio]
        with self.Session1() as session1, self.Session2() as session2:
            for model in models:
                logger.info(f"Сравнение таблицы {model.__tablename__}...")
                data_1 = self.get_all_data(session1, model)
                data_2 = self.get_all_data(session2, model)

                diff_data = self.get_differences(data_1, data_2)
                logger.info(f"Найдено различий в {model.__tablename__}: {len(diff_data)}")

                for data in diff_data:
                    logger.info(f"Различие в {model.__tablename__}: {data}")

    def get_differences(self, list1, list2):
        diff = []
        primary_key_name = list2[0].__table__.primary_key.columns.values()[0].name if list2 else 'id'
        ids_in_list2 = {getattr(item, primary_key_name) for item in list2}
        list2_dict = {getattr(item, primary_key_name): item for item in list2}

        for item in list1:
            item_id = getattr(item, primary_key_name)
            if item_id not in ids_in_list2:
                diff.append(item)
            else:
                # Сравнение значений полей
                for column in item.__table__.columns:
                    if getattr(item, column.name) != getattr(list2_dict[item_id], column.name):
                        diff.append(item)
                        break
        return diff

    def merge_databases(self, output_db_path):
        models = [Title, Episode, History, Franchise, FranchiseRelease, Poster, Schedule, Rating, Torrent,
                  ProductionStudio]
        with self.Session1() as session1, self.Session2() as session2:
            logger.info("Начало процесса мержа данных...")
            for model in models:
                data_1 = self.get_all_data(session1, model)
                data_2 = self.get_all_data(session2, model)

                merged_data = self.get_differences(data_1, data_2)

                # Добавление новых записей в первую базу данных
                primary_key_name = model.__table__.primary_key.columns.values()[0].name
                for data in merged_data:
                    session1.add(data)
                    primary_key_value = getattr(data, primary_key_name)
                    logger.info(f"Добавлена запись с id {primary_key_value} в таблицу {model.__tablename__}")

            session1.commit()
            logger.info("Процесс мержа завершён успешно.")

        # Уничтожение движков после завершения
        self.engine_1.dispose()
        self.engine_2.dispose()

        # Сохранение изменений в новый файл базы данных
        shutil.copyfile(self.engine_1.url.database, output_db_path)
        logger.info(f"Итоговая база данных сохранена в {output_db_path}")
        return output_db_path

    def merge_all_databases(self, temp_databases, output_db_path):
        """
        Объединяет все базы данных из списка temp_databases в один файл.
        """
        logger.info("Начинаем мерж всех найденных баз данных...")

        intermediate_files = []  # Список промежуточных файлов

        while len(temp_databases) > 1:
            # Берем первые две базы данных из списка
            db_path_1 = temp_databases.pop(0)
            db_path_2 = temp_databases.pop(0)

            # Создаем уникальное имя для промежуточного файла
            intermediate_output = os.path.join(
                os.path.dirname(output_db_path),
                f"intermediate_{len(temp_databases)}.db"
            )
            intermediate_files.append(intermediate_output)

            # Мержим их с использованием существующего метода merge_databases
            self.__init__(db_path_1, db_path_2)
            self.merge_databases(intermediate_output)

            # Используем результат как входной файл для следующего шага
            temp_databases.insert(0, intermediate_output)

        # Перемещаем последний файл в output_db_path
        final_intermediate = temp_databases[0]
        shutil.move(final_intermediate, output_db_path)
        logger.info(f"Все базы данных объединены в {output_db_path}")

    def generate_qr_code(self, link, qr_code_path):
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(qr_code_path)
            logger.info(f"QR-код успешно сохранен в {qr_code_path}")
        except Exception as e:
            logger.error(f"Ошибка при генерации QR-кода: {e}")

    async def async_download_from_fileio(self, url, output_path):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Ошибка при скачивании файла: {response.status} - {response.reason}")
                        return

                    total_size = int(response.headers.get('content-length', 0))
                    with open(output_path, 'wb') as f, tqdm(
                            desc="Downloading",
                            total=total_size,
                            unit='B',
                            unit_scale=True,
                            unit_divisor=1024,
                    ) as bar:
                        async for chunk in response.content.iter_chunked(1024):
                            if chunk:
                                f.write(chunk)
                                bar.update(len(chunk))
            logger.info(f"Файл успешно загружен в {output_path}")
        except Exception as e:
            logger.error(f"Ошибка при асинхронной загрузке файла: {e}")

    def upload_to_fileio_with_retries(self, file_api_key, db_path, retries=3, delay=5):
        """
        Загружает файл на file.io с указанием срока хранения (1 день).
        """
        for attempt in range(retries):
            try:
                file_size = os.path.getsize(db_path)
                with open(db_path, 'rb') as db_file, tqdm(
                        total=file_size or 1,  # Минимум 1 для корректной работы
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        desc="Uploading"
                ) as bar:
                    response = requests.post(
                        TEMP_CLOUD_API,
                        headers={
                            "Authorization": f"Bearer {file_api_key}"
                        },
                        files={'file': db_file},
                        data={"expires": "1d",
                              "maxDownloads": 1,
                              "autoDelete": "true",
                              },  # Устанавливаем срок хранения ссылки на 1 день
                        stream=True,
                        timeout=60
                    )
                    bar.update(file_size)
                    if response.status_code == 200:
                        link = response.json().get('link')
                        if link:
                            logger.info(f"Файл успешно загружен. Ссылка: {link}")
                            return link
                    else:
                        logger.error(f"Ошибка загрузки файла: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Попытка {attempt + 1} из {retries} не удалась: {e}")
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    logger.error("Все попытки загрузки файла исчерпаны.")
        return None

    def get_all_data_with_progress(session, model):
        try:
            query = session.query(model)
            total_count = query.count()  # Количество строк
            data = []
            with tqdm(total=total_count, desc=f"Fetching {model.__tablename__}") as bar:
                for item in query.yield_per(100):  # Чтение блоками для экономии памяти
                    data.append(item)
                    bar.update(1)
            return data
        except Exception as e:
            logger.error(f"Ошибка при получении данных из модели {model.__tablename__}: {e}")
            return []

    def send_email_with_postmarkapp(self, url, api_key, user_name, download_link):
        """
        Отправка письма с использованием Postmark API.
        """
        try:

            logger.info(f"url, api_key, email, download_link: {url}, {api_key}, {user_name}, {download_link}")
            # Генерация QR-кода
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            qr_code_path = QRCODE_NAME
            img.save(qr_code_path)

            # Подготовка данных для отправки
            subject = "Ссылка для скачивания"
            body = f"Скачайте базу данных по следующей ссылке: {download_link}"

            # Отправка письма
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": api_key
            }
            payload = {
                "From": user_name,
                "To": user_name,
                "Subject": subject,
                "TextBody": body
            }

            response = requests.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                logger.info(f"Письмо отправлено: {response.json()}")
            else:
                logger.error(f"Ошибка: {response.status_code}, {response.text}")

        except Exception as e:
            logger.error(f"Ошибка при отправке письма через Postmark: {e}")


if __name__ == "__main__":
    global mail_api_url, mail_api_key, email, file_api_key
    parser = argparse.ArgumentParser(description="Utility for merging SQLite databases.")
    parser.add_argument("--mail_api_key", help=" MAILGUN_API_KEY", required=True)
    parser.add_argument("--file_api_key", help="FILE_IO_API_KEY", required=False)
    parser.add_argument("--user", help="email", required=True)

    parser.add_argument("--db_path_1", help="Path to the first database", required=False)
    parser.add_argument("--db_path_2", help="Path to the second database", required=False)
    parser.add_argument("--link", help="Link to the database for merging", required=False)
    parser.add_argument("--qrcode_path", help="Path to the QR code image for merging", required=False)
    args = parser.parse_args()

    MAIL_API_KEY = args.mail_api_key  # Присваиваем переданный API ключ для почты
    FILE_IO_API_KEY = args.file_api_key  # Присваиваем переданный API ключ для file.io
    EMAIL = args.user  # Присваиваем email

    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(base_dir, 'db')
    temp_dir = os.path.join(base_dir, 'temp')

    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    final_db_path = os.path.join(db_dir, DB_NAME)
    temp_db_path = os.path.join(temp_dir, TEMP_DB_NAME)
    merged_db_path = os.path.join(db_dir, MERGED_DB_NAME)
    qr_code_path = os.path.join(temp_dir, QRCODE_NAME)

    utility = None
    if args.db_path_1 and args.db_path_2:
        # Ручной мерж двух баз данных
        utility = DatabaseMergeUtility(args.db_path_1, args.db_path_2)
        utility.compare_databases()
        utility.merge_databases(final_db_path)
    elif args.link or args.qrcode_path:
        # Скачивание базы данных по ссылке или QR-коду и мерж
        link = args.link
        if args.qrcode_path:
            img = qrcode.Image.open(args.qrcode_path)
            link = img.get_data()

        utility = DatabaseMergeUtility("", "")

        if link:
            # Асинхронное скачивание файла с прогрессом
            asyncio.run(utility.async_download_from_fileio(link, temp_db_path))

            # Проверка существования загруженного файла
            if os.path.exists(temp_db_path):
                logger.info(f"База данных успешно загружена в {temp_db_path}")

                # Поиск всех баз данных в папке temp и мерж
                temp_databases = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith('.db')]

                if len(temp_databases) > 1:
                    utility = DatabaseMergeUtility("", "")  # Пустые пути, т.к. они задаются динамически
                    utility.merge_all_databases(temp_databases, final_db_path)

                    # Загрузка в облако и отправка email
                    link = utility.upload_to_fileio_with_retries(FILE_IO_API_KEY, final_db_path, retries=3, delay=5)
                    if link:
                        utility.generate_qr_code(link, qr_code_path)
                        utility.send_email_with_postmarkapp(MAIL_API_URL, MAIL_API_KEY, EMAIL, link)
                        logger.info("Уведомление отправлено.")
            else:
                logger.error("Ошибка: база данных не была загружена.")
        else:
            logger.error("Нужно указать либо ссылку, либо путь к QR-коду.")
    else:
        # Автоматический мерж всех найденных баз данных в temp_dir
        # Список всех баз данных в папке temp
        # Список всех баз данных в папке temp
        temp_databases = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith('.db')]

        if len(temp_databases) > 1:
            logger.info(f"Найдены базы данных в temp_dir: {temp_databases}, начинаем мерж...")

            # Создаем экземпляр утилиты
            utility = DatabaseMergeUtility("", "")  # Пустые параметры, чтобы динамически задавать базы

            # Итоговый путь для объединенной базы данных
            output_db_path = os.path.join(db_dir, DB_NAME)

            # Выполняем мерж всех баз данных
            utility.merge_all_databases(temp_databases, output_db_path)

            logger.info(f"Файл базы данных объединен и сохранен в '{output_db_path}'")

            # Загрузка в облако и отправка email
            link = utility.upload_to_fileio_with_retries(FILE_IO_API_KEY, final_db_path, retries=3, delay=5)
            if link:
                utility.generate_qr_code(link, qr_code_path)
                utility.send_email_with_postmarkapp(MAIL_API_URL, MAIL_API_KEY, EMAIL, link)
                logger.info("Уведомление отправлено.")
        else:
            logger.warning("Недостаточно баз данных для выполнения мержа.")



