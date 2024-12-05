import os
import shutil
import importlib.util
from sqlalchemy import create_engine, Column, Integer, String, select, update, inspect, MetaData, Table, NullPool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.types import DateTime
from datetime import datetime


DB_FOLDER = "db"
TEMP_FOLDER = "temp"
MERGE_DB_PREFIX = "merged_"

Base = declarative_base()

TABLES_FILE_PATH = "core/tables.py"

# Динамическая загрузка модуля
def load_tables_module(file_path):
    spec = importlib.util.spec_from_file_location("tables", file_path)
    tables_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tables_module)
    return tables_module

# Загрузка модуля
tables_module = load_tables_module(TABLES_FILE_PATH)

# Получение всех таблиц из Base.metadata
def get_registered_tables(base):
    return list(base.metadata.tables.keys())

# Использование
registered_tables = get_registered_tables(tables_module.Base)
print("Зарегистрированные таблицы:", registered_tables)

REQUIRED_TABLES = {
    "titles",
    "production_studios",
    "days_of_week",
    "schedule",
    "history",
    "ratings",
    "franchise_releases",
    "franchises",
    "genres",
    "title_genre_relation",
    "team_members",
    "title_team_relation",
    "episodes",
    "torrents",
    "posters",
    "templates",
}

def validate_db(engine):
    """
    Проверка наличия таблиц и структуры в базе данных.
    Возвращает список совпадающих таблиц.
    """
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # Находим совпадающие таблицы
        matching_tables = REQUIRED_TABLES & existing_tables
        if not matching_tables:
            print(f"Нет совпадающих таблиц. Пропускаем базу данных {engine.url.database}.")
            return False, []

        # Проверяем столбцы для каждой совпадающей таблицы
        for table_name in matching_tables:
            required_columns = {
                "titles": {"title_id", "name_ru", "type_code", "last_updated"},
                "episodes": {"episode_id", "title_id", "episode_number", "created_timestamp"},
                # Дополните для остальных таблиц
            }.get(table_name, set())

            if required_columns:
                columns = {col['name'] for col in inspector.get_columns(table_name)}
                missing_columns = required_columns - columns
                if missing_columns:
                    print(f"Предупреждение: Таблица {table_name} не содержит колонок: {missing_columns}")

        print(f"БД {engine.url.database} успешно прошла гибкую валидацию.")
        return True, matching_tables

    except Exception as e:
        print(f"Ошибка при валидации базы данных {engine.url.database}: {e}")
        return False, []

def upgrade_db(engine):
    """Создание недостающих таблиц и колонок в БД."""
    try:
        tables_module.Base.metadata.create_all(engine)
        print(f"Схема базы данных {engine.url.database} обновлена.")
    except Exception as e:
        print(f"Ошибка обновления схемы БД {engine.url.database}: {e}")

def compare_and_merge(original_engine, temp_engine, merge_engine):
    """Compares and merges matching tables from the original and temporary databases into a new one."""
    with original_engine.connect() as orig_conn, \
         temp_engine.connect() as temp_conn, \
         merge_engine.connect() as merge_conn:

        # Create all tables in the new database using merge_conn
        tables_module.Base.metadata.create_all(merge_conn)

        orig_session = sessionmaker(bind=orig_conn)()
        temp_session = sessionmaker(bind=temp_conn)()
        merge_session = sessionmaker(bind=merge_conn)()

        # Reflect tables using temp_conn
        inspector = inspect(temp_conn)
        temp_tables = set(inspector.get_table_names())
        matching_tables = set(tables_module.Base.metadata.tables.keys()) & temp_tables

        if not matching_tables:
            print(f"No matching tables to merge.")
            return

        for table_name in matching_tables:
            print(f"Processing table {table_name}...")

            # Reflect the table from temp_conn
            temp_metadata = MetaData()
            temp_table = Table(table_name, temp_metadata, autoload_with=temp_conn)

            # Reflect the table from merge_conn
            merge_metadata = MetaData()
            merge_table = Table(table_name, merge_metadata, autoload_with=merge_conn)

            # Fetch data from temp_table
            temp_data = temp_session.execute(select(temp_table)).fetchall()
            print(f"Number of rows fetched from temp_table '{table_name}': {len(temp_data)}")

            # Get columns in temp_table and merge_table
            temp_columns = {col.name for col in temp_table.columns}
            merge_columns = {col.name for col in merge_table.columns}
            common_columns = temp_columns & merge_columns

            # Map columns if necessary (e.g., schedule_id to id)
            column_mapping = {}
            for col in common_columns:
                column_mapping[col] = col

            # Handle special cases where column names differ
            # Example: If 'schedule_id' in temp_table corresponds to 'id' in merge_table
            if table_name == 'schedule':
                if 'schedule_id' in temp_columns and 'id' in merge_columns:
                    column_mapping['schedule_id'] = 'id'

            # Get DateTime columns in merge_table
            datetime_columns = [col.name for col in merge_table.columns if isinstance(col.type, DateTime)]

            for row in temp_data:
                # Map row data to merge_table columns
                row_dict = dict(row._mapping)
                filtered_row = {}
                for temp_col_name, merge_col_name in column_mapping.items():
                    value = row_dict.get(temp_col_name)
                    filtered_row[merge_col_name] = value

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
                                    print(f"Warning: Unexpected data type for datetime column '{col_name}': {type(value)}")
                                    filtered_row[col_name] = None
                            except Exception as e:
                                print(f"Error parsing datetime column '{col_name}' with value '{value}': {e}")
                                filtered_row[col_name] = None

                # Exclude auto-incremented primary key columns
                primary_keys = [col for col in merge_table.columns if col.primary_key]
                for pk_col in primary_keys:
                    if pk_col.autoincrement:
                        pk_name = pk_col.name
                        if pk_name in filtered_row:
                            filtered_row.pop(pk_name)

                # Log the filtered_row
                print(f"Inserting into '{table_name}': {filtered_row}")

                if not filtered_row:
                    print(f"Filtered row is empty for table '{table_name}', skipping insert.")
                    continue

                # Use ON CONFLICT DO NOTHING to handle duplicates
                stmt = insert(merge_table).values(**filtered_row)
                conflict_columns = [key.name for key in merge_table.primary_key]
                stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)

                try:
                    result = merge_session.execute(stmt)
                    if result.rowcount == 0:
                        print(f"Row not inserted due to conflict in table '{table_name}': {filtered_row}")
                except Exception as e:
                    print(f"Error inserting into table '{table_name}': {e}")
                    print(f"Failed row: {filtered_row}")

            # Commit after each table to release locks
            merge_session.commit()

        # Close sessions
        orig_session.close()
        temp_session.close()
        merge_session.close()

def inspect_db(engine):
    """Печатает список таблиц и их колонки."""
    inspector = inspect(engine)
    print(f"Таблицы в БД {engine.url.database}:")
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        print(f" - {table_name}: {[col['name'] for col in columns]}")


def main():
    original_db = os.path.join(DB_FOLDER, "anime_player.db")
    temp_dbs = [os.path.join(TEMP_FOLDER, f) for f in os.listdir(TEMP_FOLDER) if f.endswith(".db")]

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
            print(f"Database {temp_db} did not pass validation. Applying schema upgrade.")
            upgrade_db(temp_engine)
            is_valid, _ = validate_db(temp_engine)
            if not is_valid:
                print(f"Database {temp_db} still does not meet requirements. Skipping.")
                continue

        merge_db_path = os.path.join(DB_FOLDER, f"{MERGE_DB_PREFIX}{os.path.basename(temp_db)}")

        # **Copy the original database to the merge database before merging**
        shutil.copyfile(original_db, merge_db_path)

        merge_engine = create_engine(
            f"sqlite:///{merge_db_path}",
            connect_args={'timeout': 30},
            poolclass=NullPool,
            isolation_level=None  # Set isolation_level to None for autocommit
        )

        print(f"Comparing and merging {temp_db} with {original_db}...")
        compare_and_merge(original_engine, temp_engine, merge_engine)

        if not os.path.exists(merge_db_path):
            print(f"Error: File {merge_db_path} was not created. Skipping.")
            continue

        # **Replace the original database with the merged database**
        shutil.move(merge_db_path, original_db)
        print(f"Original database updated: {original_db}")

        # Dispose of engines to release resources
        temp_engine.dispose()
        merge_engine.dispose()

    # Dispose of the original engine after all operations
    original_engine.dispose()


if __name__ == "__main__":
    main()