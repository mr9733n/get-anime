import pytest
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from merge_utility import compare_and_merge


# Utility function to set up an in-memory SQLite engine
def setup_in_memory_db():
    return create_engine("sqlite:///:memory:")


# Utility function to create example tables and data
def create_example_tables(engine, metadata, table_name, columns, extend_existing=False):
    # Create table with specified columns
    table = Table(table_name, metadata, *columns, extend_existing=extend_existing)
    metadata.create_all(engine)
    return table


@pytest.fixture
def original_engine():
    engine = setup_in_memory_db()
    yield engine
    engine.dispose()


@pytest.fixture
def temp_engine():
    engine = setup_in_memory_db()
    yield engine
    engine.dispose()


@pytest.fixture
def merge_engine():
    engine = setup_in_memory_db()
    yield engine
    engine.dispose()


def test_merge_insert_new_records(original_engine, temp_engine, merge_engine):
    metadata = MetaData()
    columns = [
        Column('title_id', Integer, primary_key=True),
        Column('name_ru', String),
        Column('last_updated', DateTime)
    ]
    original_table = create_example_tables(original_engine, metadata, 'titles', columns)
    temp_table = create_example_tables(temp_engine, metadata, 'titles', columns, extend_existing=True)
    merge_table = create_example_tables(merge_engine, metadata, 'titles', columns, extend_existing=True)

    # Insert data into the temporary table
    with temp_engine.connect() as conn:
        conn.execute(temp_table.insert(), [
            {'title_id': 1, 'name_ru': 'Temp Record 1', 'last_updated': datetime(2024, 1, 1)},
            {'title_id': 2, 'name_ru': 'Temp Record 2', 'last_updated': datetime(2024, 1, 2)}
        ])

    # Call compare_and_merge
    result = compare_and_merge(original_engine, temp_engine, merge_engine)

    # Verify that the data was inserted into the merge table
    assert result is not False
    with merge_engine.connect() as conn:
        result = conn.execute(merge_table.select()).fetchall()
        assert len(result) == 2
        assert result[0]['name_ru'] == 'Temp Record 1'
        assert result[1]['name_ru'] == 'Temp Record 2'


def test_merge_update_existing_records(original_engine, temp_engine, merge_engine):
    metadata = MetaData()
    columns = [
        Column('title_id', Integer, primary_key=True),
        Column('name_ru', String),
        Column('last_updated', DateTime)
    ]
    original_table = create_example_tables(original_engine, metadata, 'titles', columns)
    temp_table = create_example_tables(temp_engine, metadata, 'titles', columns, extend_existing=True)
    merge_table = create_example_tables(merge_engine, metadata, 'titles', columns, extend_existing=True)

    # Insert data into the original and temporary tables
    with original_engine.connect() as conn:
        conn.execute(original_table.insert(), [
            {'title_id': 1, 'name_ru': 'Original Record 1', 'last_updated': datetime(2024, 1, 1)}
        ])

    with temp_engine.connect() as conn:
        conn.execute(temp_table.insert(), [
            {'title_id': 1, 'name_ru': 'Updated Record 1', 'last_updated': datetime(2024, 1, 3)}
        ])

    # Call compare_and_merge
    result = compare_and_merge(original_engine, temp_engine, merge_engine)

    # Verify that the data was updated in the merge table
    assert result is not False
    with merge_engine.connect() as conn:
        result = conn.execute(merge_table.select()).fetchall()
        assert len(result) == 1
        assert result[0]['name_ru'] == 'Updated Record 1'
        assert result[0]['last_updated'] == datetime(2024, 1, 3)


def test_merge_no_changes(original_engine, temp_engine, merge_engine):
    metadata = MetaData()
    columns = [
        Column('title_id', Integer, primary_key=True),
        Column('name_ru', String),
        Column('last_updated', DateTime)
    ]
    original_table = create_example_tables(original_engine, metadata, 'titles', columns)
    temp_table = create_example_tables(temp_engine, metadata, 'titles', columns, extend_existing=True)
    merge_table = create_example_tables(merge_engine, metadata, 'titles', columns, extend_existing=True)

    # Insert identical data into the original and temporary tables
    with original_engine.connect() as conn:
        conn.execute(original_table.insert(), [
            {'title_id': 1, 'name_ru': 'Original Record 1', 'last_updated': datetime(2024, 1, 1)}
        ])

    with temp_engine.connect() as conn:
        conn.execute(temp_table.insert(), [
            {'title_id': 1, 'name_ru': 'Original Record 1', 'last_updated': datetime(2024, 1, 1)}
        ])

    # Call compare_and_merge
    result = compare_and_merge(original_engine, temp_engine, merge_engine)

    # Verify that no changes were made
    assert result is not False
    with merge_engine.connect() as conn:
        result = conn.execute(merge_table.select()).fetchall()
        assert len(result) == 1
        assert result[0]['name_ru'] == 'Original Record 1'
        assert result[0]['last_updated'] == datetime(2024, 1, 1)


def test_merge_two_new_records_each_db(original_engine, temp_engine, merge_engine):
    metadata = MetaData()
    columns = [



    Column('title_id', Integer, primary_key=True),
    Column('code', String, unique=True),
    Column('last_updated', DateTime, default=datetime.utcnow)
    ]
    original_table = create_example_tables(original_engine, metadata, 'titles', columns)
    temp_table = create_example_tables(temp_engine, metadata, 'titles', columns, extend_existing=True)
    merge_table = create_example_tables(merge_engine, metadata, 'titles', columns, extend_existing=True)

    # Insert data into original and temporary tables
    with original_engine.connect() as conn:
        conn.execute(original_table.insert(), [
            {'title_id': 1, 'code': 'Original Record 1', 'last_updated': datetime(2024, 1, 1)},
            {'title_id': 2, 'code': 'Original Record 2', 'last_updated': datetime(2024, 1, 2)}
        ])

    with temp_engine.connect() as conn:
        conn.execute(temp_table.insert(), [
            {'title_id': 3, 'code': 'Temp Record 1', 'last_updated': datetime(2024, 1, 3)},
            {'title_id': 4, 'code': 'Temp Record 2', 'last_updated': datetime(2024, 1, 4)}
        ])

    # Call compare_and_merge
    result = compare_and_merge(original_engine, temp_engine, merge_engine)

    # Verify that all records were merged
    assert result is not False
    with merge_engine.connect() as conn:
        result = conn.execute(merge_table.select()).fetchall()
        assert len(result) == 4


def test_merge_two_common_one_newer(original_engine, temp_engine, merge_engine):
    metadata = MetaData()
    columns = [
        Column('title_id', Integer, primary_key=True),
        Column('name_ru', String),
        Column('last_updated', DateTime)
    ]
    original_table = create_example_tables(original_engine, metadata, 'titles', columns)
    temp_table = create_example_tables(temp_engine, metadata, 'titles', columns, extend_existing=True)
    merge_table = create_example_tables(merge_engine, metadata, 'titles', columns, extend_existing=True)

    # Insert data into original and temporary tables
    with original_engine.connect() as conn:
        conn.execute(original_table.insert(), [
            {'title_id': 1, 'name_ru': 'Original Record 1', 'last_updated': datetime(2024, 1, 1)},
            {'title_id': 2, 'name_ru': 'Original Record 2', 'last_updated': datetime(2024, 1, 2)}
        ])

    with temp_engine.connect() as conn:
        conn.execute(temp_table.insert(), [
            {'title_id': 1, 'name_ru': 'Temp Record 1', 'last_updated': datetime(2024, 1, 3)},
            {'title_id': 3, 'name_ru': 'Temp Record 3', 'last_updated': datetime(2024, 1, 4)}
        ])

    # Call compare_and_merge
    result = compare_and_merge(original_engine, temp_engine, merge_engine)

    # Verify the merged results
    assert result is not False
    with merge_engine.connect() as conn:
        result = conn.execute(merge_table.select()).fetchall()
        assert len(result) == 3
        for row in result:
            if row['title_id'] == 1:
                assert row['name_ru'] == 'Temp Record 1'
                assert row['last_updated'] == datetime(2024, 1, 3)
