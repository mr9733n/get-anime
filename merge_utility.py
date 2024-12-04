import os
import shutil
import importlib.util
import time
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

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv(dotenv_path='.env')

# Constants
DB_FOLDER = "db"
TEMP_FOLDER = "temp"
MERGE_DB_PREFIX = "merged_"
TABLES_REF_FOLDER = "core"
TABLES_FILE_PATH = os.path.join(TABLES_REF_FOLDER, "tables.py")
FILE_API_URL = "https://file.io"  # Replace with the correct endpoint if necessary
POSTMARK_API_URL = "https://api.postmarkapp.com/email"

# Set your API keys and other sensitive information via environment variables
FILEIO_API_KEY = os.environ.get('FILEIO_API_KEY', '')  # Replace with your file.io API key or leave empty if not needed
POSTMARK_API_KEY = os.environ.get('POSTMARK_API_KEY')  # Replace with your Postmark API key
FROM_EMAIL = os.environ.get('FROM_EMAIL')  # Your verified sender email address
TO_EMAIL = os.environ.get('TO_EMAIL')  # Recipient email address

Base = declarative_base()

logger.info(f"Loaded FILEIO_API_KEY: {FILEIO_API_KEY}")
logger.info(f"Loaded POSTMARK_API_KEY: {POSTMARK_API_KEY}")
logger.info(f"Loaded FROM_EMAIL: {FROM_EMAIL}")
logger.info(f"Loaded TO_EMAIL: {TO_EMAIL}")

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

        conflict_columns_mapping = {
            'genres': ['name'],
            'schedule': ['day_of_week', 'title_id'],
            'days_of_week': ['day_name'],
            'templates': ['name'],
            'titles': ['code'],  # Conflict column for titles
            # Add other tables as needed
        }
        do_nothing_tables = {'titles', 'days_of_week', 'templates', 'genres'}

        for table_name in matching_tables:
            logger.info(f"Processing table {table_name}...")

            # Reflect the table from temp_conn
            temp_metadata = MetaData()
            temp_table = Table(table_name, temp_metadata, autoload_with=temp_conn)

            # Reflect the table from merge_conn
            merge_metadata = MetaData()
            merge_table = Table(table_name, merge_metadata, autoload_with=merge_conn)

            # Fetch data from temp_table
            temp_data = temp_session.execute(select(temp_table)).fetchall()

            # Get columns in temp_table and merge_table
            temp_columns = {col.name for col in temp_table.columns}
            merge_columns = {col.name for col in merge_table.columns}
            common_columns = temp_columns & merge_columns

            # Map columns if necessary
            column_mapping = {col: col for col in common_columns}

            # Handle special cases where column names differ
            # Example: If 'schedule_id' in temp_table corresponds to 'id' in merge_table
            # Adjust as needed

            # Get DateTime columns in merge_table
            datetime_columns = [col.name for col in merge_table.columns if isinstance(col.type, DateTime)]

            for row in temp_data:
                # Map row data to merge_table columns
                row_dict = dict(row._mapping)
                filtered_row = {}
                for temp_col_name, merge_col_name in column_mapping.items():
                    value = row_dict.get(temp_col_name)
                    filtered_row[merge_col_name] = value

                # Ensure all required columns are present
                required_columns = [col.name for col in merge_table.columns if not col.nullable and not col.default]
                missing_columns = [col for col in required_columns if col not in filtered_row or filtered_row[col] is None]

                if missing_columns:
                    logger.error(f"Missing required columns {missing_columns} in row for table '{table_name}'. Skipping row.")
                    continue

                # Convert datetime columns to datetime objects
                for col_name in datetime_columns:
                    if col_name in filtered_row:
                        value = filtered_row[col_name]
                        if value is not None and not isinstance(value, datetime):
                            try:
                                if isinstance(value, str):
                                    filtered_row[col_name] = datetime.fromisoformat(value)
                                elif isinstance(value, (int, float)):
                                    filtered_row[col_name] = datetime.fromtimestamp(value)
                                else:
                                    logger.warning(f"Unexpected data type for datetime column '{col_name}': {type(value)}")
                                    filtered_row[col_name] = None
                            except Exception as e:
                                logger.error(f"Error parsing datetime column '{col_name}' with value '{value}': {e}")
                                filtered_row[col_name] = None

                # Exclude auto-incremented primary key columns
                primary_keys = [col for col in merge_table.columns if col.primary_key]
                for pk_col in primary_keys:
                    if pk_col.autoincrement:
                        pk_name = pk_col.name
                        if pk_name in filtered_row:
                            filtered_row.pop(pk_name)

                # Log the filtered_row
                logger.debug(f"Inserting into '{table_name}': {filtered_row}")

                if not filtered_row:
                    logger.warning(f"Filtered row is empty for table '{table_name}', skipping insert.")
                    continue

                # Determine conflict columns
                if table_name in conflict_columns_mapping:
                    conflict_columns = conflict_columns_mapping[table_name]
                else:
                    conflict_columns = [col.name for col in merge_table.primary_key]

                # Use appropriate conflict action
                stmt = insert(merge_table).values(**filtered_row)
                if table_name in do_nothing_tables:
                    # Use DO NOTHING for tables where we don't want to update existing records
                    stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)
                else:
                    # Use DO UPDATE for other tables
                    update_columns = {col: stmt.excluded[col] for col in filtered_row.keys() if col not in conflict_columns}
                    stmt = stmt.on_conflict_do_update(index_elements=conflict_columns, set_=update_columns)

                try:
                    merge_session.execute(stmt)
                except IntegrityError as e:
                    logger.error(f"IntegrityError inserting/updating table '{table_name}': {e}")
                    logger.error(f"Failed row: {filtered_row}")
                    merge_session.rollback()
                except Exception as e:
                    logger.error(f"Error inserting/updating table '{table_name}': {e}")
                    logger.error(f"Failed row: {filtered_row}")
                    merge_session.rollback()

            # Commit after each table to release locks
            merge_session.commit()

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


def upload_to_fileio_with_retries(file_api_key, db_path, retries=3, delay=5, timeout=600):
    file_size = os.path.getsize(db_path)
    logger.info(f"Starting upload: {db_path} [{file_size}]")

    headers = {"Authorization": f"Bearer {file_api_key}"} if file_api_key else {}
    files = {"file": (os.path.basename(db_path), open(db_path, 'rb'), "application/octet-stream")}
    data = {
        "expires": "1h",  # Задать срок действия ссылки
        "maxDownloads": 1,  # Максимальное количество скачиваний
        "autoDelete": True  # Автоматическое удаление после загрузки
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
                return True, link
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
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_code_path)
        logger.info(f"QR code successfully saved to {qr_code_path}")
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")

def send_email_with_postmarkapp(api_url, api_key, from_email, to_email, download_link, qrcode_path):
    """
    Sends an email with the QR code image embedded using Postmark.
    """
    try:
        logger.info(f"api_url, api_key, from_email, to_email, download_link, qrcode_path: {api_url}, {api_key}, {from_email}, {to_email}, {download_link}, {qrcode_path}")
        # Read the QR code image and encode it in Base64
        with open(qrcode_path, 'rb') as image_file:
            img_data = base64.b64encode(image_file.read()).decode('utf-8')

        # Prepare the HTML body
        subject = "Your Download Link"
        body = f"""
        <p>Please download the database from the following link: <a href="{download_link}">{download_link}</a></p>
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
            logger.info("Email sent successfully.")
        else:
            logger.error(f"Error sending email: {response.status_code}, {response.text}")

    except Exception as e:
        logger.error(f"Error sending email via Postmark: {e}")


def main():
    global postmark_api_key, from_email, to_email, fileio_api_key
    original_db = os.path.join(DB_FOLDER, "anime_player.db")
    temp_dbs = [os.path.join(TEMP_FOLDER, f) for f in os.listdir(TEMP_FOLDER) if f.endswith(".db")]

    if POSTMARK_API_KEY and FROM_EMAIL and TO_EMAIL and FILEIO_API_KEY:
        postmark_api_key = POSTMARK_API_KEY
        from_email = FROM_EMAIL
        to_email = TO_EMAIL
        fileio_api_key = FILEIO_API_KEY
    # Backup the original database
    backup_db = os.path.join(DB_FOLDER, "anime_player_backup.db")
    if not os.path.exists(backup_db):
        shutil.copyfile(original_db, backup_db)
        logger.info(f"Original database backed up to {backup_db}")

    original_engine = create_engine(
        f"sqlite:///{original_db}",
        connect_args={'timeout': 30},
        poolclass=NullPool,
        isolation_level=None  # Set isolation_level to None for autocommit
    )

    for temp_db in temp_dbs:
        temp_engine = create_engine(
            f"sqlite:///{temp_db}",
            connect_args={'timeout': 30},
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
            connect_args={'timeout': 30},
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

    # After merging databases, perform the following steps
    merged_db_path = original_db  # The merged database is at original_db

    # Upload the merged database to the cloud
    success, download_link = upload_to_fileio_with_retries(fileio_api_key, merged_db_path)

    if success and download_link:
        # Generate QR code for the download link
        qr_code_path = os.path.join(TEMP_FOLDER, "qrcode.png")
        os.makedirs(os.path.dirname(qr_code_path), exist_ok=True)
        generate_qr_code(download_link, qr_code_path)

        # Send the QR code via email
        if postmark_api_key and from_email and to_email:

            send_email_with_postmarkapp(
                api_url=POSTMARK_API_URL,
                api_key=postmark_api_key,
                from_email=from_email,
                to_email=to_email,
                download_link=download_link,
                qrcode_path=qr_code_path
            )
        else:
            logger.error("Missing Postmark API key or email addresses. Email not sent.")

if __name__ == "__main__":
    main()
