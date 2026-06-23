from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from backend.core.dto.schedule import ScheduleItemNormalized
from backend.infra.db.schedule_sqlalchemy import SqlAlchemyScheduleReadPort, SqlAlchemyScheduleWritePort
from backend.infra.db.titles_port_sqlalchemy import SqlAlchemyTitlesPort
from storage.database_manager import DatabaseManager
from storage.tables import Episode, Genre, History, Provider, Schedule, Title, TitleGenreRelation, TitleProviderMap


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


def test_schedule_read_port_does_not_lazy_load_after_session_close(tmp_path):
    db_path = tmp_path / "schedule.sqlite"
    db = DatabaseManager(str(db_path))
    try:
        db.initialize_tables()
        updated_at = datetime(2026, 4, 26, 12, 0)
        with db.Session() as session:
            session.merge(Title(title_id=7001, name_ru="Schedule Test", is_deleted=False))
            session.merge(
                Schedule(
                    title_id=7001,
                    day_of_week=3,
                    last_updated=updated_at,
                )
            )
            session.commit()

        port = SqlAlchemyScheduleReadPort(db)

        entries = port.get_schedule_by_day(3)

        assert len(entries) == 1
        assert entries[0].title_id == 7001
        assert entries[0].day_of_week == 3
        assert entries[0].last_updated == updated_at.isoformat()
    finally:
        db.engine.dispose()


def test_schedule_replace_removes_stale_provider_rows_only(tmp_path):
    db_path = tmp_path / "schedule_replace.sqlite"
    db = DatabaseManager(str(db_path))
    try:
        db.initialize_tables()
        with db.Session() as session:
            session.merge(Provider(provider_id=1, code="aniliberty", name="AniLiberty"))
            session.merge(Provider(provider_id=2, code="animedia", name="AniMedia"))
            session.merge(Title(title_id=7101, name_ru="Stale AniLiberty", is_deleted=False))
            session.merge(Title(title_id=7102, name_ru="Current AniLiberty", is_deleted=False))
            session.merge(Title(title_id=7103, name_ru="Other Provider", is_deleted=False))
            session.merge(TitleProviderMap(provider_id=1, title_id=7101, external_title_id="stale"))
            session.merge(TitleProviderMap(provider_id=1, title_id=7102, external_title_id="current"))
            session.merge(TitleProviderMap(provider_id=2, title_id=7103, external_title_id="other"))
            session.merge(Schedule(title_id=7101, day_of_week=4))
            session.merge(Schedule(title_id=7102, day_of_week=4))
            session.merge(Schedule(title_id=7103, day_of_week=4))
            session.commit()

        item = ScheduleItemNormalized(
            provider_code="aniliberty",
            external_title_id="current",
            day_of_week=4,
            air_dt=None,
            episode_label=None,
            poster_url=None,
            title_url=None,
            raw=None,
        )
        result = SqlAlchemyScheduleWritePort(db).replace_schedule(
            provider_code="aniliberty",
            items=[item],
            days={4},
        )

        assert result.upserted == 1
        assert result.unresolved == 0
        with db.Session() as session:
            rows = (
                session.query(Schedule.title_id)
                .filter(Schedule.day_of_week == 4)
                .order_by(Schedule.title_id)
                .all()
            )
        assert [row[0] for row in rows] == [7102, 7103]
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
                    last_updated=datetime(2025, 1, 1, 12, 0),
                    is_deleted=False,
                )
            )
            session.merge(Genre(genre_id=1, name="Сёнен"))
            session.merge(
                Title(
                    title_id=9002,
                    name_ru="Recent Test",
                    name_en="Recent Test",
                    last_updated=datetime(2026, 4, 26, 12, 0),
                    is_deleted=False,
                )
            )
            session.merge(TitleGenreRelation(title_id=9001, genre_id=1))
            session.merge(History(user_id=42, title_id=9001, need_to_see=True))
            session.commit()

        port = SqlAlchemyTitlesPort(db)

        assert port.search_title_ids("kaisen", limit=10, offset=0) == [9001]
        assert port.search_title_ids("kaisen", limit=10, offset=0, year=2025) == [9001]
        assert port.search_title_ids("", limit=10, offset=0, need_to_see=True, user_id=42) == [9001]
        assert port.search_title_ids("", limit=2, offset=0, sort="recent") == [9002, 9001]
        assert port.count_search_titles("kaisen", year=2025) == 1
        assert port.count_search_titles("", need_to_see=True, user_id=42) == 1
        assert port.count_search_titles("", sort="recent") == 2
    finally:
        db.engine.dispose()
