import os
import sqlite3

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
db_path = os.path.join(ROOT_DIR, "db", "anime_player.db")

print("DB:", db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# отключаем FK (обязательно для SQLite)
cur.execute("PRAGMA foreign_keys=OFF;")
conn.commit()

try:
    # --- 1. Переименовываем старую таблицу ---
    cur.execute("ALTER TABLE titles RENAME TO titles_old;")

    # --- 2. Создаём новую таблицу БЕЗ animedia_id и provider ---
    cur.execute("""
        CREATE TABLE titles (
            title_id INTEGER PRIMARY KEY,
            code TEXT,
            name_ru TEXT NOT NULL,
            name_en TEXT,
            alternative_name TEXT,
            title_franchises TEXT,
            announce TEXT,
            status_string TEXT,
            status_code INTEGER,
            poster_path_small TEXT,
            poster_path_medium TEXT,
            poster_path_original TEXT,
            updated INTEGER,
            last_change INTEGER,
            type_full_string TEXT,
            type_code INTEGER,
            type_string TEXT,
            type_episodes INTEGER,
            type_length TEXT,
            title_genres TEXT,
            team_voice TEXT,
            team_translator TEXT,
            team_timing TEXT,
            season_string TEXT,
            season_code INTEGER,
            season_year INTEGER,
            season_week_day INTEGER,
            description TEXT,
            in_favorites INTEGER,
            blocked_copyrights BOOLEAN,
            blocked_geoip BOOLEAN,
            blocked_geoip_list TEXT,
            host_for_player TEXT,
            alternative_player TEXT,
            last_updated DATETIME
        );
    """)

    # --- 3. Переносим данные (без старых столбцов) ---
    cur.execute("""
        INSERT INTO titles (
            title_id,
            code,
            name_ru,
            name_en,
            alternative_name,
            title_franchises,
            announce,
            status_string,
            status_code,
            poster_path_small,
            poster_path_medium,
            poster_path_original,
            updated,
            last_change,
            type_full_string,
            type_code,
            type_string,
            type_episodes,
            type_length,
            title_genres,
            team_voice,
            team_translator,
            team_timing,
            season_string,
            season_code,
            season_year,
            season_week_day,
            description,
            in_favorites,
            blocked_copyrights,
            blocked_geoip,
            blocked_geoip_list,
            host_for_player,
            alternative_player,
            last_updated
        )
        SELECT
            title_id,
            code,
            name_ru,
            name_en,
            alternative_name,
            title_franchises,
            announce,
            status_string,
            status_code,
            poster_path_small,
            poster_path_medium,
            poster_path_original,
            updated,
            last_change,
            type_full_string,
            type_code,
            type_string,
            type_episodes,
            type_length,
            title_genres,
            team_voice,
            team_translator,
            team_timing,
            season_string,
            season_code,
            season_year,
            season_week_day,
            description,
            in_favorites,
            blocked_copyrights,
            blocked_geoip,
            blocked_geoip_list,
            host_for_player,
            alternative_player,
            last_updated
        FROM titles_old;
    """)

    # --- 4. Удаляем старую таблицу ---
    cur.execute("DROP TABLE titles_old;")

    conn.commit()
    print("Migration completed successfully.")

finally:
    cur.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.close()
