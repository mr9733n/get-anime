import os

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload
from core.tables import Title, Schedule, History, Rating, FranchiseRelease, Franchise, Poster, Torrent, \
    TitleGenreRelation, \
    Template, Genre, TeamMember, TitleTeamRelation, Episode, ProductionStudio, Provider, TitleProviderMap

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
db_dir1 = os.path.join(ROOT_DIR, 'db')
DB_PATH1 = os.path.join(db_dir1, 'anime_player.db')
database_url = f"sqlite:///{DB_PATH1}"

# Connect to the database
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)()

title_ids_to_delete = [10052]

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
