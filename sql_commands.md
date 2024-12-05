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

```sql
UPDATE torrents
SET uploaded_timestamp = strftime('%Y-%m-%d %H:%M:%f', uploaded_timestamp, 'unixepoch', 'localtime')
```
