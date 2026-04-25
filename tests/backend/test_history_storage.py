import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from storage.save import SaveManager
from storage.tables import Base, Episode, History, Title


def _memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def test_save_watch_all_episodes_resolves_none_to_title_episodes():
    engine, Session = _memory_db()
    manager = SaveManager(engine)
    try:
        with Session() as session:
            session.add(Title(title_id=10175, name_ru="Grand Blue"))
            session.add_all(
                [
                    Episode(episode_id=23197, title_id=10175, episode_number=1),
                    Episode(episode_id=23198, title_id=10175, episode_number=2),
                ]
            )
            session.commit()

        affected = manager.save_watch_all_episodes(
            user_id=42,
            title_id=10175,
            is_watched=True,
            episode_ids=None,
        )

        assert affected == 2
        with Session() as session:
            rows = (
                session.query(History)
                .filter_by(user_id=42, title_id=10175)
                .order_by(History.episode_id)
                .all()
            )
            assert [row.episode_id for row in rows] == [23197, 23198]
            assert [row.is_watched for row in rows] == [True, True]
    finally:
        manager.Session.close()
        engine.dispose()


def test_save_watch_all_episodes_rejects_explicit_empty_list():
    engine, Session = _memory_db()
    manager = SaveManager(engine)
    try:
        with Session() as session:
            session.add(Title(title_id=10175, name_ru="Grand Blue"))
            session.commit()

        with pytest.raises(ValueError, match="Episode IDs must be a non-empty list"):
            manager.save_watch_all_episodes(
                user_id=42,
                title_id=10175,
                is_watched=True,
                episode_ids=[],
            )
    finally:
        manager.Session.close()
        engine.dispose()
