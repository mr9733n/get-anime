import os

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload
from core.tables import Title, Schedule, History, Rating, FranchiseRelease, Franchise, Poster, Torrent, \
    TitleGenreRelation, \
    Template, Genre, TeamMember, TitleTeamRelation, Episode, ProductionStudio, Provider, TitleProviderMap

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
build_dir = os.path.join(ROOT_DIR, 'dist/AnimePlayer')
db_dir1 = os.path.join(ROOT_DIR, 'db')
db_dir2 = os.path.join(build_dir, 'db')
DB_PATH1 = os.path.join(db_dir1, 'anime_player.db')
DB_PATH2 = os.path.join(db_dir2, 'anime_player.db')
TITLE_IDS = []

# Connect to the database
database_url = f"sqlite:///{DB_PATH2}"
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)()
title_ids_to_delete = TITLE_IDS

with Session as session:
    titles = (
        session.query(Title)
        .options(
            joinedload(Title.franchises),
            joinedload(Title.genres),
            joinedload(Title.team_members),
            joinedload(Title.episodes),
            joinedload(Title.torrents),
            joinedload(Title.posters),
            joinedload(Title.schedules),
            joinedload(Title.ratings),
            joinedload(Title.history),
            joinedload(Title.production_studio),
            joinedload(Title.provider_links),
            joinedload(Title.schedules),
        )
        .filter(Title.title_id.in_(title_ids_to_delete))
        .all()
    )

    for t in titles:
        session.delete(t)

    session.commit()

print("Удалено:", len(titles), "тайтлов")

with Session as session:
    orphan_episode_ids = [
        e.episode_id
        for e in session.query(Episode).filter(Episode.title_id == None).all()
    ]

    print("Найдено эпизодов без title_id:", orphan_episode_ids)

    if orphan_episode_ids:
        deleted_episodes = (
            session.query(Episode)
            .filter(Episode.title_id == None)
            .delete(synchronize_session=False)
        )
        print("Удалено эпизодов:", deleted_episodes)

        session.commit()
    else:
        print("Эпизодов без title_id не найдено.")