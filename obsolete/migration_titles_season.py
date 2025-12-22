import os

from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from core.process import ProcessManager
from core.tables import Title

# допустим Title: season_key, season_code, season_string
# normalize_season(...) -> SeasonNorm(key, code, string, raw_string, raw_code)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
build_dir = os.path.join(ROOT_DIR, 'dist/AnimePlayer')
db_dir1 = os.path.join(ROOT_DIR, 'db')
db_dir2 = os.path.join(build_dir, 'db')
DB_PATH1 = os.path.join(db_dir1, 'anime_player.db')
DB_PATH2 = os.path.join(db_dir2, 'anime_player.db')

# Connect to the database
database_url = f"sqlite:///{DB_PATH2}"
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)

BATCH_SIZE = 1000

process = ProcessManager

def backfill_seasons(session) -> None:
    last_id = 0
    updated = 0

    while True:
        rows = session.execute(
            select(Title)
            .where(Title.title_id > last_id)
            .order_by(Title.title_id.asc())
            .limit(BATCH_SIZE)
        ).scalars().all()

        if not rows:
            break

        for t in rows:
            last_id = t.title_id

            # Собираем "сырьё" из БД. Важно: если code есть — он приоритетнее.
            season_payload = {
                "code": t.season_code,
                "string": t.season_string or "",
            }

            norm = process.normalize_season(season=season_payload, locale="en")

            # Если у записи сезон вообще пустой — можно не трогать.
            # Или наоборот: если string есть, а key/code пустые — заполним.
            changed = False

            if t.season_key != norm.key:
                t.season_key = norm.key
                changed = True

            # season_code в БД приводим к канону
            if t.season_code != norm.code:
                t.season_code = norm.code
                changed = True

            # Если хочешь ещё и строку привести в канон (например, "Spring")
            if (t.season_string or "") != norm.string:
                t.season_string = norm.string
                changed = True

            if changed:
                updated += 1

        session.commit()
        print(f"Committed batch up to title_id={last_id}, updated={updated}")

    print(f"Done. Total updated rows: {updated}")

if __name__ == "__main__":
    with Session() as session:
        backfill_seasons(session)