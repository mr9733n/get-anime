import hashlib
import os
import shutil
import sqlite3
import sys
import argparse

from datetime import datetime

import sqlalchemy
from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import sessionmaker

from core.tables import Poster


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
base_dir = os.path.join(ROOT_DIR, "midnight")
log_path = os.path.join(ROOT_DIR, "logs")
build_dir = os.path.join(ROOT_DIR, 'dist/AnimePlayer')
db_dir1 = os.path.join(ROOT_DIR, 'db')
db_dir2 = os.path.join(build_dir, 'db')
DB_PATH1 = os.path.join(db_dir1, 'anime_player.db')
DB_PATH2 = os.path.join(db_dir2, 'anime_player.db')


def backup_database(db_path):
    """Creates a backup of the database."""
    source_db_path = db_path
    backup_folder = os.path.join(os.path.expanduser("~"), "Desktop", "db")

    os.makedirs(backup_folder, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file_name = f"anime_player_{timestamp}.db"
    backup_path = os.path.join(backup_folder, backup_file_name)

    try:
        if os.path.exists(source_db_path):
            shutil.copy2(source_db_path, backup_path)
            print(f"✅ Database backup saved: {backup_path}")
            return True
        else:
            print(f"⚠️ Database file not found: {source_db_path}")
            return False
    except Exception as e:
        print(f"❌ Error copying DB: {e}")
        return False


def select_database(auto_choice=None):
    """
    Allows user to select which database to use.

    Args:
        auto_choice (str, optional): Automatically use this choice ('1' for development, '2' for production)

    Returns:
        str: Database path
    """
    # Check if both database paths exist
    path1_exists = os.path.exists(DB_PATH1)
    path2_exists = os.path.exists(DB_PATH2)

    if not path1_exists and not path2_exists:
        print("❌ Error: No database files found!")
        print(f"Development path: {DB_PATH1}")
        print(f"Production path: {DB_PATH2}")
        sys.exit(1)

    # Show database options
    print("\n=== Database Selection ===")
    print(f"1. Development DB: {DB_PATH1}" + (" [EXISTS]" if path1_exists else " [NOT FOUND]"))
    print(f"2. Production DB: {DB_PATH2}" + (" [EXISTS]" if path2_exists else " [NOT FOUND]"))

    # Set default to production (choice '2')
    default_choice = '2'

    # Get user choice or use auto_choice
    if auto_choice in ['1', '2']:
        db_choice = auto_choice
        print(f"Using {'Development' if db_choice == '1' else 'Production'} database (auto-selected)")
    else:
        # Change the prompt to indicate the default
        while True:
            db_choice = input(f"Please select database (1/2, default: {default_choice}): ").strip()
            if db_choice == '':  # Empty input means use default
                db_choice = default_choice
                print(f"Using default (Production) database")
            if db_choice in ['1', '2']:
                break
            print("Invalid choice. Please enter 1 or 2.")

    # Set database path based on choice
    if db_choice == '1':
        if not path1_exists:
            print(f"⚠️ Warning: Development database not found at {DB_PATH1}")
            if path2_exists and input("Use production database instead? (y/n): ").lower() == 'y':
                db_path = DB_PATH2
                print(f"Using production database: {DB_PATH2}")
            else:
                print("Operation cancelled.")
                sys.exit(1)
        else:
            db_path = DB_PATH1
            print(f"Using development database: {DB_PATH1}")
    else:  # db_choice == '2'
        if not path2_exists:
            print(f"⚠️ Warning: Production database not found at {DB_PATH2}")
            if path1_exists and input("Use development database instead? (y/n): ").lower() == 'y':
                db_path = DB_PATH1
                print(f"Using development database: {DB_PATH1}")
            else:
                print("Operation cancelled.")
                sys.exit(1)
        else:
            db_path = DB_PATH2
            print(f"Using production database: {DB_PATH2}")

    return db_path


def update_poster_hashes(engine):
    """Обновляет хеши для всех постеров, у которых они отсутствуют, используя прямой SQL-запрос"""
    try:
        with engine.connect() as connection:
            # Получаем все ID постеров
            result = connection.execute(
                sqlalchemy.text("SELECT poster_id, title_id FROM posters WHERE hash_value IS NULL"))
            poster_data = result.fetchall()

            if not poster_data:
                print("Все постеры уже имеют хеши или в базе нет постеров.")
                return

            print(f"Начинаем обновление хешей для {len(poster_data)} постеров...")

            updated_count = 0
            for row in poster_data:
                poster_id = row[0]
                title_id = row[1]

                # Получаем бинарные данные постера
                blob_result = connection.execute(
                    sqlalchemy.text("SELECT poster_blob FROM posters WHERE poster_id = :pid"),
                    {"pid": poster_id}
                )
                blob_data = blob_result.scalar()

                if blob_data:
                    # Вычисляем MD5-хеш из бинарных данных постера
                    hash_value = hashlib.md5(blob_data).hexdigest()

                    # Обновляем запись
                    connection.execute(
                        sqlalchemy.text("UPDATE posters SET hash_value = :hash WHERE poster_id = :pid"),
                        {"hash": hash_value, "pid": poster_id}
                    )

                    updated_count += 1

                    if updated_count % 100 == 0:  # Выводим прогресс каждые 100 записей
                        print(f"Обработано {updated_count}/{len(poster_data)} постеров...")

            connection.commit()
            print(f"✅ Успешно обновлено {updated_count} постеров.")

    except Exception as e:
        print(f"❌ Ошибка при обновлении хешей постеров: {e}")


def add_hash_column_if_not_exists(engine):
    """Добавляет столбец hash_value в таблицу posters, если его еще нет"""
    try:
        # Проверяем, существует ли столбец hash_value
        inspector = sqlalchemy.inspect(engine)
        columns = [column['name'] for column in inspector.get_columns('posters')]

        if 'hash_value' not in columns:
            print("Добавляем столбец hash_value в таблицу posters...")
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("ALTER TABLE posters ADD COLUMN hash_value VARCHAR(32)"))
            print("Столбец hash_value успешно добавлен.")
        else:
            print("Столбец hash_value уже существует в таблице posters.")
        return True
    except Exception as e:
        print(f"Ошибка при добавлении столбца hash_value: {e}")
        return False


def main(db_choice=None):
    # Выбираем базу данных
    db_path = select_database(db_choice)

    # Создаем бэкап базы данных перед изменениями
    if not backup_database(db_path):
        if input("Не удалось создать бэкап базы данных. Продолжить без бэкапа? (y/n): ").lower() != 'y':
            print("Операция отменена.")
            sys.exit(1)

    # Подключаемся к базе данных
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url)

    # Добавляем столбец hash_value, если его еще нет
    if not add_hash_column_if_not_exists(engine):
        if input("Не удалось добавить столбец hash_value. Продолжить с обновлением хешей? (y/n): ").lower() != 'y':
            print("Операция отменена.")
            sys.exit(1)

    # Обновляем хеши постеров используя прямые SQL-запросы
    update_poster_hashes(engine)

    print("Миграция завершена.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, choices=['1', '2'], help='Database to use (1=Development, 2=Production)')
    args = parser.parse_args()
    main(db_choice=args.db)