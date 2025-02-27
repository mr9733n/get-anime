import argparse
import os
import random
import shutil
import importlib.util
import sqlite3
import string
import sys
import time
import pyzipper
import qrcode
import requests
import logging
import base64

from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from sqlalchemy import create_engine, select, inspect, MetaData, Table, NullPool
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.types import DateTime
from sqlalchemy.exc import IntegrityError

STATUS = False

# Constants
DB_FOLDER = "db"
TEMP_FOLDER = "temp"
MERGE_DB_PREFIX = "merged_"
TABLES_REF_FOLDER = os.path.join("core", "__pycache__")
TABLES_REF_NAME = "tables.cpython-312.pyc"
ORIG_DB_NAME = "anime_player.db"
BACKUP_DB_NAME = "anime_player_backup.db"
QRCODE_FILE_NAME = "qrcode.png"
DOWNLOAD_DB_NAME = "downloaded.db"
LOG_FOLDER_NAME = "logs"
LOG_FILE_NAME = "merged_log.txt"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TABLES_FILE_PATH = os.path.join(TABLES_REF_FOLDER, TABLES_REF_NAME)

#Configuration
RETRIES = 3
DELAY = 5
TIMEOUT_UPLOAD = 600
TIMEOUT_DB_CONN = 30
EXPIRES = 1
MAX_DOWNLOADS = 1
AUTO_DELETE = True
QRCODE_VER = 1
QRCODE_BOX_SIZE = 6
QRCODE_BORDER = 2

# Tables to skip updating existing records (e.g., days_of_week)
TABLES_SKIP_UPDATE = {'days_of_week', 'schedule'}

# Tables conflict columns mapping
CONFLICT_COLUMNS_MAPPING = {
    'genres': ['name'],
    'schedule': ['day_of_week', 'title_id'],
    'templates': ['name'],
    'titles': ['code'],
    'episodes': ['uuid'],
    'ratings': ['title_id', 'rating_name'],
    'franchises': ['title_id', 'franchise_id'],
    'history': ['user_id', 'title_id'],  # Added relevant unique columns
    'days_of_week': ['day_of_week'],
    'team_members': ['id', 'name', 'role'],
    'title_team_relation': ['title_id', 'team_member_id'],
    'title_genre_relation': ['title_id', 'genre_id'],
    'franchise_releases': ['franchise_id', 'title_id'],
    'production_studios': ['title_id', 'name'],
    'posters': ['title_id'],
    'torrents': ['torrent_id'],
}

ORIG_COLUMNS_MAPPING = {
    "titles": {"title_id", "name_ru", "type_code", "last_updated", "updated", "last_change", "code", "name_en",
               "alternative_name", "title_franchises", "announce", "status_string", "status_code", "poster_path_small",
               "poster_path_medium", "poster_path_original", "type_full_string", "type_string", "type_episodes",
               "type_length", "title_genres", "team_voice", "team_translator", "team_timing", "season_string",
               "season_code", "season_year", "season_week_day", "description", "in_favorites", "blocked_copyrights",
               "blocked_geoip", "blocked_geoip_list", "host_for_player", "alternative_player"},
    "episodes": {"episode_id", "title_id", "episode_number", "created_timestamp", "name", "uuid", "hls_fhd", "hls_hd",
                 "hls_sd", "preview_path", "skips_opening", "skips_ending"},
    "posters": {"poster_id", "title_id", "poster_blob", "last_updated"},
    "torrents": {"torrent_id", "title_id", "uploaded_timestamp", "magnet_link", "episodes_range", "quality",
                 "quality_type", "resolution", "encoder", "leechers", "seeders", "downloads", "total_size",
                 "size_string", "url", "hash", "torrent_metadata", "raw_base64_file"},
    "schedule": {"day_of_week", "title_id", "last_updated"},
    "history": {"id", "user_id", "title_id", "episode_id", "torrent_id", "is_watched", "last_watched_at",
                "previous_watched_at", "watch_change_count", "is_download", "last_download_at", "previous_download_at",
                "download_change_count", "need_to_see"},
    "ratings": {"rating_id", "title_id", "rating_name", "rating_value", "last_updated"},
    "franchise_releases": {"id", "franchise_id", "title_id", "code", "ordinal", "name_ru", "name_en",
                           "name_alternative", "last_updated"},
    "franchises": {"id", "title_id", "franchise_id", "franchise_name", "last_updated"},
    "genres": {"genre_id", "name", "last_updated"},
    "title_genre_relation": {"id", "title_id", "genre_id", "last_updated"},
    "team_members": {"id", "name", "role", "last_updated"},
    "title_team_relation": {"id", "title_id", "team_member_id", "last_updated"},
    "production_studios": {"title_id", "name", "last_updated"},
    "days_of_week": {"day_of_week", "day_name"},
    "templates": {"id", "name", "one_title_html", "titles_html", "text_list_html", "styles_css", "created_at"},
}

# Logging configuration
log_dir = os.path.join(BASE_DIR, LOG_FOLDER_NAME)
os.makedirs(log_dir, exist_ok=True)  # Создаёт папку для логов, если её нет
LOG_FILE = os.path.join(log_dir, LOG_FILE_NAME)
# Configure logging
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=2_000_000, backupCount=10, encoding="utf-8"
)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

load_dotenv(dotenv_path='.env')

# Set your API keys and other sensitive information via environment variables
POSTMARK_API_KEY = os.environ.get('POSTMARK_API_KEY')  # Replace with your Postmark API key
FROM_EMAIL = os.environ.get('FROM_EMAIL')  # Your verified sender email address
TO_EMAIL = os.environ.get('TO_EMAIL')  # Recipient email address
FILE_API_URL = os.environ.get('FILE_API_URL')
POSTMARK_API_URL = os.environ.get('POSTMARK_API_URL')

# Base = declarative_base()
logger.info(f"*****4jk45h6-j54h-jk54hjkH-jk54-6Gj5654jk*****")
logger.info(f"Anime Player Merge Utility App version 0.0.0.2")
logger.info(f"Loaded POSTMARK_API_KEY: {'True' if POSTMARK_API_KEY else 'False'}")
logger.info(f"Loaded FROM_EMAIL: {'True' if FROM_EMAIL else 'False'}")
logger.info(f"Loaded TO_EMAIL: {'True' if TO_EMAIL else 'False'}")
logger.info(f"Loaded FILE_API_URL: {'True' if FILE_API_URL else 'False'}")
logger.info(f"Loaded POSTMARK_API_URL: {'True' if POSTMARK_API_URL else 'False'}")

def load_tables_module(file_path):
    spec = importlib.util.spec_from_file_location("tables", file_path)
    tables_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tables_module)
    return tables_module

# Load tables module
tables_module = load_tables_module(TABLES_FILE_PATH)

# Get registered tables from Base.metadata
def get_registered_tables(base):
    return list(base.metadata.tables.keys())

# Get registered tables
registered_tables = get_registered_tables(tables_module.Base)
logger.info("Registered tables: %s", registered_tables)

REQUIRED_TABLES = set(registered_tables)

def validate_db(engine):
    """
    Validates the presence of required tables and columns in the database.
    Returns a tuple (is_valid, matching_tables).
    """
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # Find matching tables
        matching_tables = REQUIRED_TABLES & existing_tables
        if not matching_tables:
            logger.warning(f"No matching tables found. Skipping database {engine.url.database}.")
            return False, []

        # Validate columns in each table
        for table_name in matching_tables:
            required_columns = ORIG_COLUMNS_MAPPING.get(table_name, set())

            if required_columns:
                columns = {col['name'] for col in inspector.get_columns(table_name)}
                missing_columns = required_columns - columns
                if missing_columns:
                    logger.warning(f"Table {table_name} is missing columns: {missing_columns}")

        logger.info(f"Database {engine.url.database} passed validation.")
        return True, matching_tables

    except Exception as e:
        logger.error(f"Error validating database {engine.url.database}: {e}")
        return False, []

# Upgrade database
def upgrade_db(engine):
    """Creates missing tables and columns in the database."""
    try:
        from core.tables import Base
        Base.metadata.create_all(engine)
        logger.info(f"Schema of database {engine.url.database} upgraded.")
    except Exception as e:
        logger.error(f"Error upgrading schema of database {engine.url.database}: {e}")

def compare_and_merge(original_engine, temp_engine, merge_engine):
    """Compares and merges matching tables from the original and temporary databases into the merge database."""
    try:
        with original_engine.connect() as orig_conn, \
             temp_engine.connect() as temp_conn, \
             merge_engine.connect() as merge_conn:

            update_count = 0
            insert_count = 0
            existed_count = 0

            orig_session = sessionmaker(bind=orig_conn)()
            temp_session = sessionmaker(bind=temp_conn)()
            merge_session = sessionmaker(bind=merge_conn)()

            inspector = inspect(temp_conn)
            temp_tables = set(inspector.get_table_names())
            matching_tables = set(tables_module.Base.metadata.tables.keys()) & temp_tables

            if not matching_tables:
                logger.warning(f"No matching tables to merge.")
                return

            for table_name in matching_tables:
                logger.info(f"Processing table {table_name}...")

                if table_name in TABLES_SKIP_UPDATE:
                    logger.info(f"Skipping table {table_name} as it's marked as static.")
                    continue

                # Reflect tables
                original_table = Table(table_name, MetaData(), autoload_with=orig_conn)
                temp_table = Table(table_name, MetaData(), autoload_with=temp_conn)
                merge_table = Table(table_name, MetaData(), autoload_with=temp_conn)

                # Get DateTime columns
                datetime_columns = [col.name for col in original_table.columns if isinstance(col.type, DateTime)]
                conflict_columns = CONFLICT_COLUMNS_MAPPING.get(table_name, [col.name for col in merge_table.primary_key])

                # Ensure conflict_columns is a list of strings, not nested lists
                if not all(isinstance(col, str) for col in conflict_columns):
                    raise ValueError(f"Conflict columns for table '{table_name}' should be a list of column names.")

                # Fetch all data from temp_table and original_table
                temp_data = temp_session.execute(select(temp_table)).fetchall()
                orig_data = orig_session.execute(select(original_table)).fetchall()

                # Choose the data from the table that has values
                if not orig_data and temp_data:
                    orig_data = temp_data
                    logger.info(f"No data found in original table '{table_name}', using data from temporary table.")
                elif not temp_data and orig_data:
                    temp_data = orig_data
                    logger.info(f"No data found in temporary table '{table_name}', using data from original table.")

                # Convert original data rows to dictionary form
                orig_data_dict = {
                    tuple(row._mapping[col] for col in conflict_columns): row._mapping for row in orig_data
                }

                for temp_row in temp_data:
                    temp_filtered_row = dict(temp_row._mapping)

                    # Determine if this row exists in the original data
                    key = tuple(temp_filtered_row[col] for col in conflict_columns)
                    existing_record = orig_data_dict.get(key)

                    # Get the primary key columns
                    primary_keys = [col.name for col in merge_table.primary_key]

                    if existing_record:
                        # Detailed logging for existing records
                        #logger.debug(f"Existing record found for table '{table_name}', key: {key}")
                        existed_count += 1
                        # Find a suitable DateTime column to compare if available
                        update_needed = False
                        for datetime_column in datetime_columns:
                            temp_value = temp_filtered_row.get(datetime_column)
                            orig_value = existing_record.get(datetime_column)

                            # Normalize values if they are not None
                            temp_timestamp = normalize_datetime(temp_value) if temp_value is not None else None
                            orig_timestamp = normalize_datetime(orig_value) if orig_value is not None else None

                            # Determine if an update is needed
                            if temp_timestamp is not None and orig_timestamp is None:
                                # Original is None, so we want to update with the value from temp
                                update_needed = True
                                update_count += 1
                                break
                            elif temp_timestamp is None and orig_timestamp is not None:
                                # Temp is None, original has value, so no update needed
                                continue
                            elif temp_timestamp is not None and orig_timestamp is not None:
                                # Both values are present, compare them
                                if temp_timestamp > orig_timestamp:
                                    update_needed = True
                                    update_count += 1
                                    break

                        # Update if required
                        if update_needed:
                            # Remove primary key columns from the update values
                            update_values = {
                                k: v for k, v in temp_filtered_row.items() if k not in primary_keys
                            }
                            merge_session.execute(
                                merge_table.update()
                                .where(*[merge_table.c[col] == temp_filtered_row[col] for col in conflict_columns])
                                .values(**update_values)
                            )
                            update_count += 1
                            #logger.info(f"Record updated in table '{table_name}', key: {key}")

                    else:
                        # Insert new record if not found in original
                        try:
                            merge_session.execute(insert(merge_table).values(**temp_filtered_row))
                            insert_count += 1
                        except IntegrityError as e:
                            # Handle unique constraint errors by removing the conflicting primary key
                            logger.warning(f"Unique constraint error on insert. Generating new primary key for '{table_name}': {e}")
                            for pk in primary_keys:
                                temp_filtered_row.pop(pk, None)  # Remove existing primary key to let the DB generate a new one
                            merge_session.execute(insert(merge_table).values(**temp_filtered_row))
                            insert_count += 1

                # Log summary statistics
                logger.info(
                    f"Merge summary: {update_count} records updated, {insert_count} records inserted, {existed_count} records existed.")
                merge_session.commit()

        logger.info("Merge completed.")
        return True
    except Exception as e:
        error_message = f"An error occurred while processing Merge: {str(e)}"
        logger.error(error_message)
        return False


# Normalize DateTime fields
def normalize_datetime(dt):
    if dt is None:
        return None
    return dt.replace(microsecond=0, tzinfo=None)

def inspect_db(engine):
    """Prints the list of tables and their columns in the database."""
    inspector = inspect(engine)
    logger.info(f"Tables in database {engine.url.database}:")
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        logger.info(f" - {table_name}: {[col['name'] for col in columns]}")


def upload_to_nullpointer_with_retries(db_path, retries=RETRIES, delay=DELAY, timeout=TIMEOUT_UPLOAD):
    """
    Загружает запароленный архив (AES-256) с исходного файла db_path на сервис Null Pointer.

    Шаги:
      1. Берётся исходный файл и формируется имя архива (.zip) на основе его имени.
      2. Генерируется случайный пароль.
      3. Создаётся зашифрованный архив с использованием AES-256.
      4. Архив загружается на сервер.

    Возвращает:
        tuple: (True, download_link, password, response_json) при успешной загрузке,
               где response_json имеет вид:
               {
                   "url": <response_text>,
                   "file_size": <archive_size>,
                   "password": <password>
               }
               иначе (False, None, None, response_data)
    """
    original_file_size = os.path.getsize(db_path)
    logging.info(f"Starting upload of {db_path} ({original_file_size} bytes)")
    print(f"Starting upload of {db_path} ({original_file_size} bytes)")

    # Формируем имя архива: используем только имя файла и добавляем ".zip"
    base_name = os.path.splitext(db_path)[0]
    archive_path = base_name + ".zip"

    # Генерируем случайный пароль (например, 12 символов)
    password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(12))

    # Создаём зашифрованный архив с AES-256 с помощью pyzipper
    try:
        with pyzipper.AESZipFile(archive_path, 'w',
                                 compression=pyzipper.ZIP_DEFLATED,
                                 encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(password.encode('utf-8'))
            # Сохраняем в архиве исходный файл с его оригинальным именем
            zf.write(db_path, arcname=os.path.basename(db_path))
        logging.info(f"Encrypted archive created: {archive_path} with password: {password}")
        print(f"Encrypted archive created: {archive_path} with password: {password}")
    except Exception as e:
        logging.error(f"Error creating encrypted archive: {e}")
        return False, None, None, None

    # Получаем размер архива
    archive_size = os.path.getsize(archive_path)
    logging.info(f"Starting upload of {archive_path} ({archive_size} bytes)")
    print(f"Starting upload of {archive_path} ({archive_size} bytes)")

    headers = {}  # Если авторизация не требуется

    try:
        file_stream = open(archive_path, 'rb')
    except Exception as e:
        logging.error(f"Cannot open file {archive_path}: {e}")
        return False, None, None, None

    original_filename = os.path.basename(archive_path)
    print(f"Uploading file with name: {original_filename}")

    files = {
        "file": (original_filename, file_stream, "application/zip")
    }

    data = {
        "expires": EXPIRES,  # например, "24" для 24 часов или "1h"
        "secret": ""  # пустая строка, чтобы сгенерировать сложный URL
    }

    for attempt in range(retries):
        try:
            response = requests.post(
                FILE_API_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=timeout
            )
            logging.info(f"Response status: {response.status_code}")
            response_text = response.text.strip()
            logging.info(f"Response text: {response_text}")
            print(f"Response text: {response_text}")

            if response.status_code == 200:
                logging.info("File successfully uploaded.")
                # Формируем итоговый словарь с данными
                response_json = {
                    "link": response_text,
                    "size": archive_size,
                    "password": password
                }
                file_stream.close()

                # If uploaded -> try to remove archive
                try:
                    os.remove(archive_path)
                    logger.info(f"Temporary archive {archive_path} removed.")
                except Exception as e:
                    logger.error(f"Error removing temporary archive {archive_path}: {e}")

                return True, response_text, password, response_json
            else:
                logging.error(f"Upload error: {response.status_code} - {response_text}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error during file upload: {e}")

        logging.warning(f"Attempt {attempt + 1} failed. Retrying in {delay} seconds...")
        time.sleep(delay)

    file_stream.close()
    return False, None, None, None

def generate_qr_code(link, qr_code_path):
    try:
        qr = qrcode.QRCode(
            version=QRCODE_VER,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=QRCODE_BOX_SIZE,
            border=QRCODE_BORDER,
        )
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_code_path)
        logger.info(f"QR code successfully saved to {qr_code_path}")
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")

def send_email_with_postmarkapp(api_url, api_key, from_email, to_email, download_link, password, qrcode_path, response_json):
    """
    Sends an email with the QR code image embedded using Postmark.
    """
    try:
        # Read the QR code image and encode it in Base64
        with open(qrcode_path, 'rb') as image_file:
            img_data = base64.b64encode(image_file.read()).decode('utf-8')

        # Prepare the HTML body
        subject = "Your Download Link"
        body = f"""
        <p>Please download the database from the following link: <a href="{download_link}">{download_link}</a></p>
        <p>Password: {password}</p>
        <p>Response JSON Data: {response_json}</p>
        <p>Or scan the QR code below:</p>
        <img src="data:image/png;base64,{img_data}">
        """

        # Prepare headers and payload
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": api_key
        }

        payload = {
            "From": from_email,
            "To": to_email,
            "Subject": subject,
            "HtmlBody": body
        }

        # Send the email
        response = requests.post(api_url, json=payload, headers=headers)

        if response.status_code == 200:
            logger.info(f"Email sent successfully. {response.json()}")
        else:
            logger.error(f"Error sending email: {response.status_code}, {response.text}")

    except Exception as e:
        logger.error(f"Error sending email via Postmark: {e}")

def is_valid_sqlite_file(file_path):
    """Проверяет, является ли файл корректной базой данных SQLite."""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    if os.path.getsize(file_path) == 0:
        logger.error(f"File is empty: {file_path}")
        return False

    try:
        with sqlite3.connect(file_path) as conn:
            conn.execute("PRAGMA integrity_check;")
        logger.info(f"File is a valid SQLite database: {file_path}")
        return True
    except sqlite3.DatabaseError:
        logger.error(f"File is not a valid SQLite database: {file_path}")
        return False

# Use DatabaseManager to initialize tables
def initialize_merge_database(db_path):
    from core.database_manager import DatabaseManager
    db_manager = DatabaseManager(db_path)
    db_manager.initialize_tables()
    db_manager.save_template(template_name='default')
    db_manager.save_placeholders()

def main():
    global postmark_api_key, from_email, to_email, fileio_api_key

    start_time = time.time()

    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Anime Player Merge Utility App version 0.0.0.2')
    parser.add_argument('--skip-merge', action='store_true', help='Skip the merging process')
    parser.add_argument('--merge-error-ignore', action='store_true', help='Start unstable merging process')
    parser.add_argument('--skip-upload-email', action='store_true', help='Skip uploading and sending email')
    parser.add_argument('--skip-email', action='store_true', help='Skip sending email')
    args = parser.parse_args()

    original_db = os.path.join(DB_FOLDER, ORIG_DB_NAME)
    temp_dir = os.path.join(BASE_DIR, TEMP_FOLDER)
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    temp_dbs = [os.path.join(TEMP_FOLDER, f) for f in os.listdir(TEMP_FOLDER) if f.endswith(".db")]

    valid_temp_dbs = []
    invalid_temp_dbs = []

    for temp_db in temp_dbs:
        if is_valid_sqlite_file(temp_db):
            valid_temp_dbs.append(temp_db)
        else:
            logger.error(f"Invalid database file: {temp_db}. Marking for deletion.")
            invalid_temp_dbs.append(temp_db)

    # Delete invalid databases if no valid ones are found
    if not valid_temp_dbs:
        logger.error("No valid database files found in TEMP_FOLDER.")
        for invalid_db in invalid_temp_dbs:
            try:
                os.remove(invalid_db)
                logger.info(f"Deleted invalid database file: {invalid_db}")
            except Exception as e:
                logger.error(f"Failed to delete invalid database file: {invalid_db}. Error: {e}")

    logger.info(f"Valid databases: {valid_temp_dbs}")

    print("Anime Player Merge Utility App version 0.0.0.2")
    print(f"This utility merges temporary databases from the {TEMP_FOLDER}")
    print(f"The merged database will then be uploaded to the cloud.")
    print(f"Original database: '{original_db}'")
    print(f"Temporary databases: '{temp_dbs}'")
    print(f"Logs: {LOG_FILE}")
    print(f"Please wait until the process is complete. The timeout for this operation is 5 minutes.")

    if POSTMARK_API_KEY and FROM_EMAIL and TO_EMAIL:
        postmark_api_key = POSTMARK_API_KEY
        from_email = FROM_EMAIL
        to_email = TO_EMAIL

    # TODO: Fix this
    if args.skip_merge and args.skip_email:
        print(f"Can not use --skip_merge and --skip_email together. Exit..")
        sys.exit(1)

    if not args.skip_merge:
       logger.info(f"Merge algorithm skipped cuz unstable.."
                   f"to enable use --merge-error-ignore")
    if args.merge_error_ignore:
       # Backup the original database
       backup_db = os.path.join(DB_FOLDER, BACKUP_DB_NAME)
       if not os.path.exists(backup_db):
           shutil.copyfile(original_db, backup_db)
           logger.info(f"Original database backed up to {backup_db}")

       original_engine = create_engine(
           f"sqlite:///{original_db}",
           connect_args={'timeout': TIMEOUT_DB_CONN},
           poolclass=NullPool
       )

       # Replace the previous table creation code with the following
       merge_db_path = os.path.join(DB_FOLDER, f"{MERGE_DB_PREFIX}{os.path.basename(ORIG_DB_NAME)}")
       initialize_merge_database(merge_db_path)

       merge_engine = create_engine(
           f"sqlite:///{merge_db_path}",
           connect_args={'timeout': TIMEOUT_DB_CONN},
           poolclass=NullPool,
           isolation_level=None  # Set isolation_level to None for autocommit
       )

       if not os.path.exists(merge_db_path):
           logger.error(f"Error: File {merge_db_path} was not created. Skipping.")

       for temp_db in temp_dbs:
           temp_engine = create_engine(
               f"sqlite:///{temp_db}",
               connect_args={'timeout': TIMEOUT_DB_CONN},
               poolclass=NullPool
           )
           inspect_db(temp_engine)

           # Upgrade the temp_db schema to match the current schema
           upgrade_db(temp_engine)
           is_valid, _ = validate_db(temp_engine)
           if not is_valid:
               logger.warning(f"Database {temp_db} did not pass validation. Skipping.")
               continue

           file_size_original_db = round(os.path.getsize(original_db) / (1024 * 1024), 2)
           file_size_temp_db = round(os.path.getsize(temp_db) / (1024 * 1024), 2)
           logger.info(f"{original_db} (file size: {file_size_original_db} MB).")
           logger.info(f"{temp_db} (file size: {file_size_temp_db} MB).")

           logger.info(f"Comparing and merging {original_db} with {original_db}...")
           status1 = compare_and_merge(original_engine, temp_engine, merge_engine)
           logger.info(f"Comparing and merging {temp_db} with {original_db}...")
           status2 = False
           # status2 = compare_and_merge(temp_engine, original_engine, merge_engine)

           # Dispose of engines to release resources
           temp_engine.dispose()

           if status1 or status2:
               # Delete the temp database file after merging
               try:
                   os.remove(temp_db)
                   logger.info(f"Temporary database {temp_db} deleted after merging.")
                   #os.remove(backup_db)
                   #logger.info(f"Backup database {backup_db} deleted after merging.")
               except Exception as e:
                   logger.error(f"Error deleting temporary database {temp_db}: {e}")
                   logger.error(f"Error deleting backup database {backup_db}: {e}")
           else:
               logger.info(f"Merging orig->temp: {status1}, Merging temp->orig: {status2}"
                           f"\nTemporary database {temp_db} cannot be deleted.")

       #
       # Dispose of the original engine after all operations
       original_engine.dispose()
       merge_engine.dispose()

       # Replace the original database with the merged database
       shutil.move(merge_db_path, original_db)
       logger.info(f"Original database updated: {original_db}")

    else:
        logger.info("Merge process skipped as per user request.")

    # After merging databases, perform the following steps
    merged_db_path = original_db  # The merged database is at original_db

    if not args.skip_upload_email:
        # Upload the merged database to the cloud
        success, download_link, password, response_json = upload_to_nullpointer_with_retries(merged_db_path)

        if success and download_link:
            # Generate QR code for the download link
            qr_code_path = os.path.join(TEMP_FOLDER, QRCODE_FILE_NAME)
            os.makedirs(os.path.dirname(qr_code_path), exist_ok=True)
            if response_json == {}:
                generate_qr_code(download_link, qr_code_path)
            else:
                generate_qr_code(response_json, qr_code_path)

            if not args.skip_email:
                # Send the QR code via email
                if postmark_api_key and from_email and to_email:
                    send_email_with_postmarkapp(
                        api_url=POSTMARK_API_URL,
                        api_key=postmark_api_key,
                        from_email=from_email,
                        to_email=to_email,
                        download_link=download_link,
                        password = password,
                        qrcode_path=qr_code_path,
                        response_json=response_json
                    )
                else:
                    logger.error("Missing Postmark API key or email addresses. Email not sent.")
            else:
                logger.info("Email sending skipped as per user request.")
        else:
            logger.error("Failed to upload the merged database.")
    else:
        logger.info("Upload and email sending skipped as per user request.")

    print(f"Finished.")
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Execution time: {elapsed_time:.2f} seconds.")
    sys.exit(0)
if __name__ == "__main__":
    main()

