***SQL-запросы для поиска и удаления дубликатов в таблицах:***

1. **Таблица `ratings`**:
```sql
WITH duplicates AS (
    SELECT title_id, rating_name, MIN(rating_id) AS keep_id
    FROM ratings
    GROUP BY title_id, rating_name
    HAVING COUNT(*) > 1
)
DELETE FROM ratings
WHERE rating_id NOT IN (SELECT keep_id FROM duplicates)
AND (title_id, rating_name) IN (SELECT title_id, rating_name FROM duplicates);
```

2. **Таблица `franchises`**:
```sql
WITH duplicates AS (
    SELECT title_id, franchise_id, MIN(id) AS keep_id
    FROM franchises
    GROUP BY title_id, franchise_id
    HAVING COUNT(*) > 1
)
DELETE FROM franchises
WHERE id NOT IN (SELECT keep_id FROM duplicates)
AND (title_id, franchise_id) IN (SELECT title_id, franchise_id FROM duplicates);
```

3. **Таблица `franchise_releases`**:
```sql
WITH duplicates AS (
    SELECT franchise_id, title_id, MIN(id) AS keep_id
    FROM franchise_releases
    GROUP BY franchise_id, title_id
    HAVING COUNT(*) > 1
)
DELETE FROM franchise_releases
WHERE id NOT IN (SELECT keep_id FROM duplicates)
AND (franchise_id, title_id) IN (SELECT franchise_id, title_id FROM duplicates);
```

4. **Таблица `genres`**:
```sql
WITH duplicates AS (
    SELECT name, MIN(genre_id) AS keep_id
    FROM genres
    GROUP BY name
    HAVING COUNT(*) > 1
)
DELETE FROM genres
WHERE genre_id NOT IN (SELECT keep_id FROM duplicates)
AND name IN (SELECT name FROM duplicates);
```

5. **Таблица `title_genre_relation`**:
```sql
WITH duplicates AS (
    SELECT title_id, genre_id, MIN(id) AS keep_id
    FROM title_genre_relation
    GROUP BY title_id, genre_id
    HAVING COUNT(*) > 1
)
DELETE FROM title_genre_relation
WHERE id NOT IN (SELECT keep_id FROM duplicates)
AND (title_id, genre_id) IN (SELECT title_id, genre_id FROM duplicates);
```

6. **Таблица `team_members`**:
```sql
WITH duplicates AS (
    SELECT name, role, MIN(id) AS keep_id
    FROM team_members
    GROUP BY name, role
    HAVING COUNT(*) > 1
)
DELETE FROM team_members
WHERE id NOT IN (SELECT keep_id FROM duplicates)
AND (name, role) IN (SELECT name, role FROM duplicates);
```

7. **Таблица `title_team_relation`**:
```sql
WITH duplicates AS (
    SELECT title_id, team_member_id, MIN(id) AS keep_id
    FROM title_team_relation
    GROUP BY title_id, team_member_id
    HAVING COUNT(*) > 1
)
DELETE FROM title_team_relation
WHERE id NOT IN (SELECT keep_id FROM duplicates)
AND (title_id, team_member_id) IN (SELECT title_id, team_member_id FROM duplicates);
```

8. Add 'last_updated' then update with current time
```sql
ALTER TABLE ratings ADD COLUMN last_updated TIMESTAMP;
ALTER TABLE franchises ADD COLUMN last_updated TIMESTAMP;
ALTER TABLE franchise_releases ADD COLUMN last_updated TIMESTAMP;
ALTER TABLE genres ADD COLUMN last_updated TIMESTAMP;
ALTER TABLE title_genre_relation ADD COLUMN last_updated TIMESTAMP;
ALTER TABLE team_members ADD COLUMN last_updated TIMESTAMP;
ALTER TABLE title_team_relation ADD COLUMN last_updated TIMESTAMP;

UPDATE ratings SET last_updated = strftime('%Y-%m-%d %H:%M:%f', 'now') || '000';
UPDATE franchises SET last_updated = strftime('%Y-%m-%d %H:%M:%f', 'now') || '000';
UPDATE franchise_releases SET last_updated = strftime('%Y-%m-%d %H:%M:%f', 'now') || '000';
UPDATE genres SET last_updated = strftime('%Y-%m-%d %H:%M:%f', 'now') || '000';
UPDATE title_genre_relation SET last_updated = strftime('%Y-%m-%d %H:%M:%f', 'now') || '000';
UPDATE team_members SET last_updated = strftime('%Y-%m-%d %H:%M:%f', 'now') || '000';
UPDATE title_team_relation SET last_updated = strftime('%Y-%m-%d %H:%M:%f', 'now') || '000';
```

9. Update 'uploaded_timestamp' from unix epoch to datetime
```sql
UPDATE torrents
SET uploaded_timestamp = strftime('%Y-%m-%d %H:%M:%f', uploaded_timestamp, 'unixepoch', 'localtime');
UPDATE torrents
SET uploaded_timestamp = uploaded_timestamp || '000';
```

9. Update 'last_change', 'updated' from unix epoch to datetime
```sql
UPDATE titles
SET updated = updated || '.000000'
WHERE updated NOT LIKE '%.%';
UPDATE titles
SET last_change = last_change || '.000000'
WHERE last_change NOT LIKE '%.%';
UPDATE titles
SET updated = strftime('%Y-%m-%d %H:%M:%f000000', updated, 'unixepoch', 'localtime')
WHERE LENGTH(updated) <= 10 AND updated GLOB '[0-9]*';
UPDATE titles
SET last_change = strftime('%Y-%m-%d %H:%M:%f000000', last_change, 'unixepoch', 'localtime')
WHERE LENGTH(last_change) <= 10 AND last_change GLOB '[0-9]*';
```
10. Update 'title_id' foreign key
    10. Check foreign key count 0
    10. Update 'title_id' foreign key in Titles
```sql
SELECT 
    'franchise_releases' as table_name, 
    (SELECT COUNT(*) FROM franchise_releases WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'franchises' as table_name, 
    (SELECT COUNT(*) FROM franchises WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'posters' as table_name, 
    (SELECT COUNT(*) FROM posters WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'torrents' as table_name, 
    (SELECT COUNT(*) FROM torrents WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'title_genre_relation' as table_name, 
    (SELECT COUNT(*) FROM title_genre_relation WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'title_team_relation' as table_name, 
    (SELECT COUNT(*) FROM title_team_relation WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'episodes' as table_name, 
    (SELECT COUNT(*) FROM episodes WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'schedule' as table_name, 
    (SELECT COUNT(*) FROM schedule WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'ratings' as table_name, 
    (SELECT COUNT(*) FROM ratings WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'history' as table_name, 
    (SELECT COUNT(*) FROM history WHERE title_id = ?) as record_count
UNION ALL
SELECT 
    'production_studios' as table_name, 
    (SELECT COUNT(*) FROM production_studios WHERE title_id = ?) as record_count;
```
```sql
UPDATE titles SET title_id = ? WHERE title_id = ?; 
```

11. Select titles without poster
```sql
SELECT t.title_id, t.code, t.name_en
FROM titles t
LEFT JOIN posters p ON t.title_id = p.title_id
WHERE p.poster_id IS NULL
```

12. fix day_of_week for api v1
```sql
-- 0) Посмотреть распределение до апдейта (по желанию)
SELECT day_of_week, COUNT(*) 
FROM schedule 
GROUP BY day_of_week 
ORDER BY 1;

-- 1) Выключаем проверку внешних ключей на время апдейта
PRAGMA foreign_keys = OFF;

-- 2) Сдвигаем 0–6 -> 1–7 (NULL и >=7/<=-1 не трогаем)
UPDATE schedule
SET day_of_week = day_of_week + 1
WHERE day_of_week BETWEEN 0 AND 6;

-- 3) Включаем проверку FK обратно
PRAGMA foreign_keys = ON;

-- 4) Проверяем, что всё согласовано
PRAGMA foreign_key_check;

-- 5) Контрольное распределение после апдейта
SELECT day_of_week, COUNT(*) 
FROM schedule 
GROUP BY day_of_week 
ORDER BY 1; 
```

13. fix torrent url for api v1
```sql
-- Обновляем URL торрентов со старого формата на новый
-- Работает только если есть hash (иначе пропускаем)

UPDATE torrents
SET url = '/api/v1/anime/torrents/' || hash || '/file'
WHERE (
    url LIKE '/public/torrent/%' 
    OR url LIKE '/storage/torrents/%'
)
AND hash IS NOT NULL 
AND hash != '';

-- Проверка результата:
SELECT 
    COUNT(*) as updated_count
FROM torrents
WHERE url LIKE '/api/v1/anime/torrents/%/file';

-- Проверка оставшихся старых URL:
SELECT 
    torrent_id,
    title_id,
    url,
    hash
FROM torrents
WHERE (
    url LIKE '/public/torrent/%' 
    OR url LIKE '/storage/torrents/%'
)
LIMIT 10; 
```

14. fixes for torrents table
```sql
ALTER TABLE torrents ADD COLUMN api_updated_at   TEXT DEFAULT NULL;
ALTER TABLE torrents ADD COLUMN is_in_production INTEGER DEFAULT 0;
ALTER TABLE torrents ADD COLUMN episodes_total   INTEGER DEFAULT 0;
ALTER TABLE torrents ADD COLUMN label            TEXT;
ALTER TABLE torrents ADD COLUMN filename         TEXT;

ALTER TABLE torrents ADD COLUMN range_first      INTEGER DEFAULT NULL;
ALTER TABLE torrents ADD COLUMN range_last       INTEGER DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_torrents_title                 ON torrents(title_id);
CREATE INDEX IF NOT EXISTS idx_torrents_title_range           ON torrents(title_id, episodes_range);
CREATE INDEX IF NOT EXISTS idx_torrents_title_res_enc         ON torrents(title_id, resolution, encoder);
CREATE INDEX IF NOT EXISTS idx_torrents_covering              ON torrents(title_id, resolution, encoder, range_first, range_last);
CREATE INDEX IF NOT EXISTS idx_torrents_title_q_enc_rng       ON torrents(title_id, quality, encoder, episodes_range);
```

15. New columns for AniMedia provider
```sql
ALTER TABLE ratings ADD COLUMN name_external TEXT DEFAULT NULL;
ALTER TABLE ratings ADD COLUMN score_external FLOAT DEFAULT NULL;

ALTER TABLE titles ADD COLUMN animedia_id INTEGER DEFAULT NULL;
ALTER TABLE titles ADD COLUMN provider INTEGER DEFAULT NULL;
UPDATE titles SET provider = 'AniLiberty';
```

16. USE IF NEEDED
```sql
ALTER TABLE episodes ADD COLUMN hls_hd_animedia TEXT DEFAULT NULL;
ALTER TABLE episodes ADD COLUMN hls_sd_animedia TEXT DEFAULT NULL;
ALTER TABLE episodes DROP COLUMN hls_hd_animedia;
ALTER TABLE episodes DROP COLUMN hls_sd_animedia;
```

17. Remove UNIQ for studio name
```sql
BEGIN TRANSACTION;

CREATE TABLE production_studios_new (
    title_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    last_updated DATETIME,
    PRIMARY KEY (title_id),
    FOREIGN KEY(title_id) REFERENCES titles (title_id)
);

INSERT INTO production_studios_new (title_id, name, last_updated)
SELECT title_id, name, last_updated FROM production_studios;

DROP TABLE production_studios;

ALTER TABLE production_studios_new RENAME TO production_studios;

COMMIT;
```

18. Fix providers
```sql
-- providers
CREATE TABLE providers (
    provider_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    code          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL
);

-- title_provider_map
CREATE TABLE title_provider_map (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title_id         INTEGER NOT NULL,
    provider_id      INTEGER NOT NULL,
    external_title_id TEXT NOT NULL,
    FOREIGN KEY (title_id) REFERENCES titles(title_id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES providers(provider_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_title_provider_external
ON title_provider_map (provider_id, external_title_id);
```
 
19. Migration for Fix providers
```sql
INSERT INTO providers (code, name)
SELECT DISTINCT LOWER(provider) AS code,
       provider                  AS name
FROM titles
WHERE provider IS NOT NULL;
```

20. Move title_id to title_provider_map
```sql
INSERT INTO title_provider_map (title_id, provider_id, external_title_id)
SELECT
    t.title_id,
    p.provider_id,
    CASE
        WHEN t.provider = 'animedia' AND t.animedia_id IS NOT NULL
            THEN CAST(t.animedia_id AS TEXT)
        ELSE CAST(t.title_id AS TEXT)
    END AS external_title_id
FROM titles t
JOIN providers p ON p.code = t.provider;
```

21. Set to lower
```sql
UPDATE providers
SET code = LOWER(code)
WHERE code IS NOT NULL;
```

22. Add new columns
```sql
ALTER TABLE franchise_releases ADD COLUMN ext_fr_id;
ALTER TABLE franchise_releases ADD COLUMN ext_fr_rel_id;
ALTER TABLE franchise_releases ADD COLUMN ext_rel_id;
ALTER TABLE titles ADD COLUMN season_key;
```

23. verify after backfill
```sql
-- неизвестные сезоны (должно быть мало или 0)
SELECT season_string, COUNT(*)
FROM titles
WHERE season_key IS NULL OR season_key = 'unknown'
GROUP BY season_string
ORDER BY COUNT(*) DESC;

-- несостыковки key<->code
SELECT season_key, season_code, COUNT(*)
FROM titles
GROUP BY season_key, season_code
ORDER BY season_key, season_code;
```

24. Check after normalisation season
```sql
SELECT season_key, season_code, COUNT(*)
FROM titles
GROUP BY season_key, season_code
ORDER BY season_key, season_code;

SELECT season_string, COUNT(*)
FROM titles
WHERE season_key='unknown'
GROUP BY season_string
ORDER BY COUNT(*) DESC;
```

25. New poster fields
```sql
ALTER TABLE posters ADD COLUMN thumb_blob BLOB;
ALTER TABLE posters ADD COLUMN thumb_hash TEXT;
ALTER TABLE posters ADD COLUMN thumb_updated_at INTEGER;

ALTER TABLE posters ADD COLUMN medium_blob BLOB;
ALTER TABLE posters ADD COLUMN medium_hash TEXT;
ALTER TABLE posters ADD COLUMN medium_updated_at INTEGER;
```

26. Fixes for Poster Migration
```sql
SELECT DISTINCT p.title_id
FROM posters p
LEFT JOIN titles t ON t.title_id = p.title_id
WHERE t.title_id IS NULL;
```

26.1 Poster migration
```sql
-- (опционально) чтобы не споткнуться о FK в процессе копирования
PRAGMA foreign_keys = OFF;

ALTER TABLE posters RENAME TO posters_old;

CREATE TABLE posters (
    poster_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title_id INTEGER NOT NULL,
    poster_blob BLOB NULL,
    hash_value TEXT NULL,
    last_updated DATETIME NULL,
    medium_blob BLOB NULL,
    medium_hash TEXT NULL,
    medium_updated_at DATETIME NULL,
    thumb_blob BLOB NULL,
    thumb_hash TEXT NULL,
    thumb_updated_at DATETIME NULL,
    FOREIGN KEY(title_id) REFERENCES titles(title_id)
);

-- ВАЖНО: если сироты нельзя удалять, то в posters с FK они не вставятся.
-- Поэтому либо вставляй только валидные...
INSERT INTO posters (
    poster_id, title_id,
    poster_blob, hash_value, last_updated,
    medium_blob, medium_hash, medium_updated_at,
    thumb_blob, thumb_hash, thumb_updated_at
)
SELECT
    p.poster_id, p.title_id,
    p.poster_blob, p.hash_value, p.last_updated,
    p.medium_blob, p.medium_hash, p.medium_updated_at,
    p.thumb_blob, p.thumb_hash, p.thumb_updated_at
FROM posters_old p
WHERE EXISTS (SELECT 1 FROM titles t WHERE t.title_id = p.title_id);

-- ...а сирот сохрани отдельно:
CREATE TABLE IF NOT EXISTS posters_orphans (
    poster_id INTEGER PRIMARY KEY,
    title_id INTEGER NOT NULL,
    poster_blob BLOB NULL,
    hash_value TEXT NULL,
    last_updated DATETIME NULL,
    medium_blob BLOB NULL,
    medium_hash TEXT NULL,
    medium_updated_at DATETIME NULL,
    thumb_blob BLOB NULL,
    thumb_hash TEXT NULL,
    thumb_updated_at DATETIME NULL,
    orphaned_at DATETIME DEFAULT (CURRENT_TIMESTAMP)
);

INSERT INTO posters_orphans (
    poster_id, title_id,
    poster_blob, hash_value, last_updated,
    medium_blob, medium_hash, medium_updated_at,
    thumb_blob, thumb_hash, thumb_updated_at
)
SELECT
    p.poster_id, p.title_id,
    p.poster_blob, p.hash_value, p.last_updated,
    p.medium_blob, p.medium_hash, p.medium_updated_at,
    p.thumb_blob, p.thumb_hash, p.thumb_updated_at
FROM posters_old p
WHERE NOT EXISTS (SELECT 1 FROM titles t WHERE t.title_id = p.title_id);

DROP TABLE posters_old;

PRAGMA foreign_keys = ON;
```

26.2 Delete orphans
```sql
DROP TABLE posters_orphans;
```