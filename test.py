import pytest
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from merge_utility import compare_and_merge


# Utility function to set up an in-memory SQLite engine
def setup_in_memory_db():
    return create_engine("sqlite:///:memory:")


# Utility function to create example tables and data
def create_example_tables(engine, metadata, extend_existing=False):
    # Original table
    table = Table('example_table', metadata,
                  Column('id', Integer, primary_key=True),
                  Column('name', String),
                  Column('last_updated', DateTime),
                  extend_existing=extend_existing
                  )
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
    original_table = create_example_tables(original_engine, metadata)
    temp_table = create_example_tables(temp_engine, metadata, extend_existing=True)
    merge_table = create_example_tables(merge_engine, metadata, extend_existing=True)

    # Insert data into the temporary table
    with temp_engine.connect() as conn:
        conn.execute(temp_table.insert(), [
            {'id': 1, 'name': 'Temp Record 1', 'last_updated': datetime(2024, 1, 1)},
            {'id': 2, 'name': 'Temp Record 2', 'last_updated': datetime(2024, 1, 2)}
        ])

    # Call compare_and_merge
    result = compare_and_merge(original_engine, temp_engine, merge_engine)

    # Verify that the data was inserted into the merge table
    assert result is not False
    with merge_engine.connect() as conn:
        result = conn.execute(merge_table.select()).fetchall()
        assert len(result) == 2
        assert result[0]['name'] == 'Temp Record 1'
        assert result[1]['name'] == 'Temp Record 2'


def test_merge_update_existing_records(original_engine, temp_engine, merge_engine):
    metadata = MetaData()
    original_table = create_example_tables(original_engine, metadata)
    temp_table = create_example_tables(temp_engine, metadata, extend_existing=True)
    merge_table = create_example_tables(merge_engine, metadata, extend_existing=True)

    # Insert data into the original and temporary tables
    with original_engine.connect() as conn:
        conn.execute(original_table.insert(), [
            {'id': 1, 'name': 'Original Record 1', 'last_updated': datetime(2024, 1, 1)}
        ])

    with temp_engine.connect() as conn:
        conn.execute(temp_table.insert(), [
            {'id': 1, 'name': 'Updated Record 1', 'last_updated': datetime(2024, 1, 3)}
        ])

    # Call compare_and_merge
    result = compare_and_merge(original_engine, temp_engine, merge_engine)

    # Verify that the data was updated in the merge table
    assert result is not False
    with merge_engine.connect() as conn:
        result = conn.execute(merge_table.select()).fetchall()
        assert len(result) == 1
        assert result[0]['name'] == 'Updated Record 1'
        assert result[0]['last_updated'] == datetime(2024, 1, 3)


def test_merge_no_changes(original_engine, temp_engine, merge_engine):
    metadata = MetaData()
    original_table = create_example_tables(original_engine, metadata)
    temp_table = create_example_tables(temp_engine, metadata, extend_existing=True)
    merge_table = create_example_tables(merge_engine, metadata, extend_existing=True)

    # Insert identical data into the original and temporary tables
    with original_engine.connect() as conn:
        conn.execute(original_table.insert(), [
            {'id': 1, 'name': 'Original Record 1', 'last_updated': datetime(2024, 1, 1)}
        ])

    with temp_engine.connect() as conn:
        conn.execute(temp_table.insert(), [
            {'id': 1, 'name': 'Original Record 1', 'last_updated': datetime(2024, 1, 1)}
        ])

    # Call compare_and_merge
    result = compare_and_merge(original_engine, temp_engine, merge_engine)

    # Verify that no changes were made
    assert result is not False
    with merge_engine.connect() as conn:
        result = conn.execute(merge_table.select()).fetchall()
        assert len(result) == 1
        assert result[0]['name'] == 'Original Record 1'
        assert result[0]['last_updated'] == datetime(2024, 1, 1)
