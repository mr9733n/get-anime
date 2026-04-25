from concurrent.futures import ThreadPoolExecutor

from backend.infra.db.titles_port_sqlalchemy import SqlAlchemyTitlesPort
from storage.database_manager import DatabaseManager
from storage.tables import Episode, Genre, Title, TitleGenreRelation


def test_get_titles_from_db_uses_request_local_sessions(tmp_path):
    db_path = tmp_path / "race.sqlite"
    db = DatabaseManager(str(db_path))
    try:
        db.initialize_tables()
        with db.Session() as session:
            session.merge(Title(title_id=10162, name_ru="Race Test", is_deleted=False))
            session.merge(
                Episode(
                    episode_id=1,
                    title_id=10162,
                    episode_number=1,
                    name="Episode 1",
                )
            )
            session.commit()

        def read_titles(_):
            return len(db.get_titles_from_db(show_all=True, title_id=10162))

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(read_titles, range(80)))

        assert results == [1] * 80
    finally:
        db.engine.dispose()


def test_titles_port_search_uses_session_factory(tmp_path):
    db_path = tmp_path / "search.sqlite"
    db = DatabaseManager(str(db_path))
    try:
        db.initialize_tables()
        with db.Session() as session:
            session.merge(
                Title(
                    title_id=9001,
                    name_ru="Магическая битва",
                    name_en="Jujutsu Kaisen",
                    season_year=2025,
                    status_string="Завершён",
                    type_string="TV",
                    is_deleted=False,
                )
            )
            session.merge(Genre(genre_id=1, name="Сёнен"))
            session.merge(TitleGenreRelation(title_id=9001, genre_id=1))
            session.commit()

        port = SqlAlchemyTitlesPort(db)

        assert port.search_title_ids("kaisen", limit=10, offset=0) == [9001]
        assert port.search_title_ids("kaisen", limit=10, offset=0, year=2025) == [9001]
        assert port.count_search_titles("kaisen", year=2025) == 1
    finally:
        db.engine.dispose()
