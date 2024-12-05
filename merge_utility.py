import argparse
import os
import shutil
import importlib.util
import sqlite3
import sys
import time
from logging.handlers import RotatingFileHandler
from tempfile import tempdir

from dotenv import load_dotenv
import requests
import logging
import base64

from tqdm import tqdm
from sqlalchemy import create_engine, Column, Integer, String, select, update, inspect, MetaData, Table, NullPool, \
    UniqueConstraint
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.types import DateTime
from datetime import datetime
import qrcode
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError

# Constants
DB_FOLDER = "db"
TEMP_FOLDER = "temp"
MERGE_DB_PREFIX = "merged_"
TABLES_REF_FOLDER = "core"
TABLES_REF_NAME = "tables.py"
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
EXPIRES = "1h"
MAX_DOWNLOADS = 1
AUTO_DELETE = True
QRCODE_VER = 1
QRCODE_BOX_SIZE = 6
QRCODE_BORDER = 2

# Tables conflict columns mapping
CONFLICT_COLUMNS_MAPPING = {
    'genres': ['name'],
    'schedule': ['day_of_week', 'title_id'],
    'templates': ['name'],
    'titles': ['title_id'],
    'episodes': ['uuid'],
    'production_studios': ['name'],
    'title_genre_relation': ['title_id', 'genre_id'],
    'title_team_relation': ['title_id', 'team_member_id'],
    'ratings': ['title_id', 'rating_name'],
    'franchise_releases': ['franchise_id', 'title_id'],
    'franchises': ['franchise_id'],
    'history': ['title_id'],
    # Add other tables as needed
}

# Tables to skip updating existing records (e.g., days_of_week)
TABLES_SKIP_UPDATE = {'days_of_week'}

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
FILEIO_API_KEY = os.environ.get('FILEIO_API_KEY', '')  # Replace with your file.io API key or leave empty if not needed
POSTMARK_API_KEY = os.environ.get('POSTMARK_API_KEY')  # Replace with your Postmark API key
FROM_EMAIL = os.environ.get('FROM_EMAIL')  # Your verified sender email address
TO_EMAIL = os.environ.get('TO_EMAIL')  # Recipient email address
FILE_API_URL = os.environ.get('FILE_API_URL')
POSTMARK_API_URL = os.environ.get('POSTMARK_API_URL')

# Base = declarative_base()
logger.info(f"*****4jk45h6-j54h-jk54hjkH-jk54-6Gj5654jk*****")
logger.info(f"Anime Player Merge Utility App version 0.0.0.1")
logger.info(f"Loaded FILEIO_API_KEY: {'True' if FILEIO_API_KEY else 'False'}")
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

        # Optionally, validate columns in each table
        for table_name in matching_tables:
            # Define required columns for validation if necessary
            required_columns = {
                "titles": {"title_id", "name_ru", "type_code", "last_updated"},
                "episodes": {"episode_id", "title_id", "episode_number", "created_timestamp"},
                # Add required columns for other tables as needed
            }.get(table_name, set())

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

def upgrade_db(engine):
    """Creates missing tables and columns in the database."""
    try:
        tables_module.Base.metadata.create_all(engine)
        logger.info(f"Schema of database {engine.url.database} upgraded.")
    except Exception as e:
        logger.error(f"Error upgrading schema of database {engine.url.database}: {e}")

def compare_and_merge(original_engine, temp_engine, merge_engine):
    """Compares and merges matching tables from the original and temporary databases into the merge database."""
    with original_engine.connect() as orig_conn, \
         temp_engine.connect() as temp_conn, \
         merge_engine.connect() as merge_conn:

        orig_session = sessionmaker(bind=orig_conn)()
        temp_session = sessionmaker(bind=temp_conn)()
        merge_session = sessionmaker(bind=merge_conn)()

        # Reflect tables using temp_conn
        inspector = inspect(temp_conn)
        temp_tables = set(inspector.get_table_names())
        matching_tables = set(tables_module.Base.metadata.tables.keys()) & temp_tables

        if not matching_tables:
            logger.warning(f"No matching tables to merge.")
            return

        conflict_columns_mapping = CONFLICT_COLUMNS_MAPPING
        # Tables to skip updating existing records (e.g., days_of_week)
        tables_skip_update = TABLES_SKIP_UPDATE

        update_count = 0
        insert_count = 0
        skip_update_count = 0

        for table_name in matching_tables:
            logger.info(f"Processing table {table_name}...")

            # Reflect the tables
            temp_metadata = MetaData()
            temp_table = Table(table_name, temp_metadata, autoload_with=temp_conn)

            merge_metadata = MetaData()
            merge_table = Table(table_name, merge_metadata, autoload_with=merge_conn)

            # Get columns
            temp_columns = {col.name for col in temp_table.columns}
            merge_columns = {col.name for col in merge_table.columns}
            common_columns = temp_columns & merge_columns

            # Map columns
            column_mapping = {col: col for col in common_columns}

            # Get DateTime columns
            datetime_columns = [col.name for col in merge_table.columns if isinstance(col.type, DateTime)]

            # Prepare conflict columns
            conflict_columns = conflict_columns_mapping.get(table_name, [col.name for col in merge_table.primary_key])

            # Fetch all data from temp_table
            temp_data = temp_session.execute(select(temp_table)).fetchall()

            for temp_row in temp_data:
                # Map row data to merge_table columns
                temp_row_dict = dict(temp_row._mapping)
                temp_filtered_row = {merge_col_name: temp_row_dict.get(temp_col_name) for temp_col_name, merge_col_name in column_mapping.items()}

                # Ensure all required columns are present
                required_columns = [col.name for col in merge_table.columns if not col.nullable and col.default is None]
                missing_columns = [col for col in required_columns if temp_filtered_row.get(col) is None]

                if missing_columns:
                    logger.error(f"Missing required columns {missing_columns} in row for table '{table_name}'. Skipping row.")
                    continue

                # Exclude auto-incremented primary key columns from temp_filtered_row for updates
                primary_keys = [col for col in merge_table.columns if col.primary_key]
                update_values = temp_filtered_row.copy()
                for pk_col in primary_keys:
                    if pk_col.autoincrement:
                        pk_name = pk_col.name
                        if pk_name in update_values:
                            update_values.pop(pk_name)

                # Convert datetime columns in temp_filtered_row
                for col_name in datetime_columns:
                    if col_name in temp_filtered_row:
                        value = temp_filtered_row[col_name]
                        if value is not None and not isinstance(value, datetime):
                            try:
                                if isinstance(value, str):
                                    temp_filtered_row[col_name] = datetime.fromisoformat(value)
                                elif isinstance(value, (int, float)):
                                    temp_filtered_row[col_name] = datetime.fromtimestamp(value)
                                else:
                                    logger.warning(f"Unexpected data type for datetime column '{col_name}': {type(value)}")
                                    temp_filtered_row[col_name] = None
                            except Exception as e:
                                logger.error(f"Error parsing datetime column '{col_name}' with value '{value}': {e}")
                                temp_filtered_row[col_name] = None

                # Build the filter condition based on conflict columns
                filter_condition = [merge_table.c[col] == temp_filtered_row[col] for col in conflict_columns]

                # Check if the record exists in the original database
                existing_record = merge_session.execute(select(merge_table).where(*filter_condition)).fetchone()

                if existing_record:
                    # Record exists, check if update is necessary
                    update_needed = False
                    for key, value in temp_filtered_row.items():
                        if existing_record._mapping[key] != value:
                            update_needed = True
                            break

                    if update_needed:
                        try:
                            update_stmt = (
                                merge_table.update()
                                .where(*filter_condition)
                                .values(**temp_filtered_row)
                            )
                            merge_session.execute(update_stmt)
                            merge_session.commit()
                            update_count += 1
                        except IntegrityError as e:
                            logger.error(f"Error updating record in table '{table_name}': {e}")
                            merge_session.rollback()
                    else:
                        skip_update_count += 1
                else:
                    # Record does not exist, insert it
                    try:
                        insert_stmt = insert(merge_table).values(**temp_filtered_row)
                        merge_session.execute(insert_stmt)
                        merge_session.commit()
                        insert_count += 1
                    except IntegrityError as e:
                        logger.error(f"Error inserting record into table '{table_name}': {e}")
                        merge_session.rollback()

            # Commit after each table to release locks
            merge_session.commit()

        # Log summary statistics
        logger.info(f"Merge summary: {update_count} records updated, {insert_count} records inserted, {skip_update_count} records skipped.")

        # Close sessions
        orig_session.close()
        temp_session.close()
        merge_session.close()

def inspect_db(engine):
    """Prints the list of tables and their columns in the database."""
    inspector = inspect(engine)
    logger.info(f"Tables in database {engine.url.database}:")
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        logger.info(f" - {table_name}: {[col['name'] for col in columns]}")


def upload_to_fileio_with_retries(file_api_key, db_path, retries=RETRIES, delay=DELAY, timeout=TIMEOUT_UPLOAD):
    file_size = os.path.getsize(db_path)
    logger.info(f"Starting upload: {db_path} [{file_size}]")

    headers = {"Authorization": f"Bearer {file_api_key}"} if file_api_key else {}
    files = {"file": (os.path.basename(db_path), open(db_path, 'rb'), "application/octet-stream")}
    data = {
        "expires": EXPIRES,
        "maxDownloads": MAX_DOWNLOADS,
        "autoDelete": AUTO_DELETE
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

            if response.status_code == 200:
                logger.info("Файл успешно загружен.")
                response_data = response.json()
                logger.info(f"Response JSON: {response_data}")
                link = response_data.get('link')
                if not link:
                    logger.error("Ссылка отсутствует в ответе сервера.")
                    return False, None
                return True, link, response.json()
            else:
                logger.error(f"Ошибка загрузки файла: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при загрузке: {e}")

        logger.warning(f"Попытка {attempt + 1} загрузки не удалась. Повтор через {delay} секунд...")
        time.sleep(delay)

    return False, None


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

def send_email_with_postmarkapp(api_url, api_key, from_email, to_email, download_link, qrcode_path, response_json):
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


def main():
    global postmark_api_key, from_email, to_email, fileio_api_key

    start_time = time.time()

    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Anime Player Merge Utility App version 0.0.0.1')
    parser.add_argument('--skip-merge', action='store_true', help='Skip the merging process')
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

    print("Anime Player Merge Utility App version 0.0.0.1")
    print(f"This utility merges temporary databases from the {TEMP_FOLDER}")
    print(f"The merged database will then be uploaded to the cloud.")
    print(f"Original database: '{original_db}'")
    print(f"Temporary databases: '{temp_dbs}'")
    print(f"Logs: {LOG_FILE}")
    print(f"Please wait until the process is complete. The timeout for this operation is 5 minutes.")

    if POSTMARK_API_KEY and FROM_EMAIL and TO_EMAIL and FILEIO_API_KEY:
        postmark_api_key = POSTMARK_API_KEY
        from_email = FROM_EMAIL
        to_email = TO_EMAIL
        fileio_api_key = FILEIO_API_KEY

    # TODO: Fix this
    if args.skip_merge and args.skip_email:
        print(f"Can not use --skip_merge and --skip_email together. Exit..")
        sys.exit(1)

    if not args.skip_merge:
        # Backup the original database
        backup_db = os.path.join(DB_FOLDER, BACKUP_DB_NAME)
        if not os.path.exists(backup_db):
            shutil.copyfile(original_db, backup_db)
            logger.info(f"Original database backed up to {backup_db}")

        original_engine = create_engine(
            f"sqlite:///{original_db}",
            connect_args={'timeout': TIMEOUT_DB_CONN},
            poolclass=NullPool,
            isolation_level=None  # Set isolation_level to None for autocommit
        )

        for temp_db in temp_dbs:
            temp_engine = create_engine(
                f"sqlite:///{temp_db}",
                connect_args={'timeout': TIMEOUT_DB_CONN},
                poolclass=NullPool,
                isolation_level=None  # Set isolation_level to None for autocommit
            )
            inspect_db(temp_engine)

            # Upgrade the temp_db schema to match the current schema
            upgrade_db(temp_engine)
            is_valid, _ = validate_db(temp_engine)
            if not is_valid:
                logger.warning(f"Database {temp_db} did not pass validation. Skipping.")
                continue

            merge_db_path = os.path.join(DB_FOLDER, f"{MERGE_DB_PREFIX}{os.path.basename(temp_db)}")

            # Copy the original database to the merge database before merging
            shutil.copyfile(original_db, merge_db_path)

            merge_engine = create_engine(
                f"sqlite:///{merge_db_path}",
                connect_args={'timeout': TIMEOUT_DB_CONN},
                poolclass=NullPool,
                isolation_level=None  # Set isolation_level to None for autocommit
            )

            logger.info(f"Comparing and merging {temp_db} with {original_db}...")
            compare_and_merge(original_engine, temp_engine, merge_engine)

            if not os.path.exists(merge_db_path):
                logger.error(f"Error: File {merge_db_path} was not created. Skipping.")
                continue

            # Replace the original database with the merged database
            shutil.move(merge_db_path, original_db)
            logger.info(f"Original database updated: {original_db}")

            # Dispose of engines to release resources
            temp_engine.dispose()
            merge_engine.dispose()

            # Delete the temp database file after merging
            try:
                os.remove(temp_db)
                logger.info(f"Temporary database {temp_db} deleted after merging.")
            except Exception as e:
                logger.error(f"Error deleting temporary database {temp_db}: {e}")

        # Dispose of the original engine after all operations
        original_engine.dispose()
    else:
        logger.info("Merge process skipped as per user request.")

    # After merging databases, perform the following steps
    merged_db_path = original_db  # The merged database is at original_db

    if not args.skip_upload_email:
        # Upload the merged database to the cloud
        success, download_link, response_json = upload_to_fileio_with_retries(fileio_api_key, merged_db_path)

        if success and download_link:
            # Generate QR code for the download link
            qr_code_path = os.path.join(TEMP_FOLDER, QRCODE_FILE_NAME)
            os.makedirs(os.path.dirname(qr_code_path), exist_ok=True)
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

