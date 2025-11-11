#!/usr/bin/env python3
import argparse, sqlite3, time, sys
from contextlib import closing

NOW = int(time.time())

def open_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    return con

def fetch_all(con, sql, args=()):
    return con.execute(sql, args).fetchall()

def fetch_one(con, sql, args=()):
    return con.execute(sql, args).fetchone()

def to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}

def coalesce(a, b):
    return a if a not in (None, "") else b

def same(val1, val2):
    # сравнение с учётом типов/NULL
    return (val1 == val2) or (val1 in ("", None) and val2 in ("", None))

def upsert_generic(cur_dst, table, pk_cols, row_src: dict, overwrite_cols=None, fill_only_cols=None, set_cols=None):
    """
    Универсальный апдейт: если запись есть, то:
      - overwrite_cols: всегда перезаписать значением из source (если не NULL)
      - fill_only_cols: заполнить только если dest пусто/NULL/'' (иначе оставить)
      - set_cols: точечные присваивания (lambda dest_val, src_val -> new_val)
      - остальные: если src НЕ пуст — перезаписать, иначе оставить
    """
    overwrite_cols = set(overwrite_cols or [])
    fill_only_cols = set(fill_only_cols or [])
    set_cols = set_cols or {}

    # найти существующую запись
    where = " AND ".join([f"{c} = ?" for c in pk_cols])
    row_dst = cur_dst.execute(f"SELECT * FROM {table} WHERE {where}",
                              tuple(row_src[c] for c in pk_cols)).fetchone()

    if row_dst is None:
        # INSERT
        cols = list(row_src.keys())
        vals = [row_src[c] for c in cols]
        placeholders = ", ".join(["?"] * len(cols))
        cur_dst.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})", vals)
        return "insert"

    # UPDATE (собираем новые значения)
    row_dst = to_dict(row_dst)
    new_vals = dict(row_dst)
    changed = False
    for col, src_val in row_src.items():
        if col in pk_cols:
            continue
        dst_val = row_dst.get(col)

        if col in set_cols:
            nv = set_cols[col](dst_val, src_val)
            if not same(nv, dst_val):
                new_vals[col] = nv
                changed = True
            continue

        if col in overwrite_cols:
            nv = src_val if src_val not in (None,) else dst_val
            if not same(nv, dst_val):
                new_vals[col] = nv
                changed = True
            continue

        if col in fill_only_cols:
            if (dst_val in (None, "")) and (src_val not in (None, "")):
                new_vals[col] = src_val
                changed = True
            continue

        # default: если src НЕ пуст — берём src, иначе оставляем
        if (src_val not in (None, "")) and not same(src_val, dst_val):
            new_vals[col] = src_val
            changed = True

    if changed:
        set_clause = ", ".join([f"{c} = ?" for c in new_vals.keys() if c not in pk_cols])
        args = [new_vals[c] for c in new_vals.keys() if c not in pk_cols] + [row_src[c] for c in pk_cols]
        cur_dst.execute(f"UPDATE {table} SET {set_clause} WHERE {where}", args)
        return "update"
    return "skip"

def merge_days_of_week(src, dst, stats):
    rows = fetch_all(src, "SELECT day_of_week, day_name FROM days_of_week")
    with dst:
        cur = dst.cursor()
        for r in rows:
            op = upsert_generic(cur, "days_of_week", ["day_of_week"], dict(r), overwrite_cols={"day_name"})
            stats["days_of_week"][op] += 1

def merge_genres(src, dst, stats):
    rows = fetch_all(src, "SELECT genre_id, name, last_updated FROM genres")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            # ключ по name, т.к. id автогенерится и может отличаться
            # если жанр с таким name уже есть — используем его id
            ex = fetch_one(dst, "SELECT genre_id FROM genres WHERE name = ?", (data["name"],))
            if ex:
                # обновляем по name (минимально, name уникален)
                op = upsert_generic(cur, "genres", ["genre_id"], {
                    "genre_id": ex["genre_id"],
                    "name": data["name"],
                    "last_updated": data["last_updated"],
                }, overwrite_cols={"name", "last_updated"})
                stats["genres"][op] += 1
            else:
                # вставляем как есть: id может быть своим
                op = upsert_generic(cur, "genres", ["genre_id"], data, overwrite_cols={"name", "last_updated"})
                stats["genres"][op] += 1

def merge_team_members(src, dst, stats):
    rows = fetch_all(src, "SELECT id, name, role, last_updated FROM team_members")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            # устойчивый ключ: (name, role)
            ex = fetch_one(dst, "SELECT id FROM team_members WHERE name = ? AND role = ?", (data["name"], data["role"]))
            if ex:
                op = upsert_generic(cur, "team_members", ["id"], {
                    "id": ex["id"], "name": data["name"], "role": data["role"],
                    "last_updated": data["last_updated"]
                }, overwrite_cols={"name", "role", "last_updated"})
            else:
                op = upsert_generic(cur, "team_members", ["id"], data, overwrite_cols={"name","role","last_updated"})
            stats["team_members"][op] += 1

def merge_titles(src, dst, stats):
    # возьмём все колонки, кроме blobs
    cols = [c[1] for c in fetch_all(src, "PRAGMA table_info(titles)")]
    rows = fetch_all(src, f"SELECT {', '.join(cols)} FROM titles")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            # локальную last_updated — на "сейчас"
            if "last_updated" in data:
                data["last_updated"] = sqlite3.TimestampFromTicks(NOW)
            op = upsert_generic(cur, "titles", ["title_id"], data, overwrite_cols=set(cols) - {"last_updated"})
            stats["titles"][op] += 1

def merge_production_studio(src, dst, stats):
    if not fetch_one(src, "SELECT name FROM sqlite_master WHERE type='table' AND name='production_studios'"):
        return
    rows = fetch_all(src, "SELECT title_id, name, last_updated FROM production_studios")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            op = upsert_generic(cur, "production_studios", ["title_id"], data, overwrite_cols={"name","last_updated"})
            stats["production_studios"][op] += 1

def merge_schedule(src, dst, stats):
    rows = fetch_all(src, "SELECT day_of_week, title_id, last_updated FROM schedule")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            op = upsert_generic(cur, "schedule", ["day_of_week","title_id"], data, overwrite_cols={"last_updated"})
            stats["schedule"][op] += 1

def merge_episodes(src, dst, stats):
    cols = [c[1] for c in fetch_all(src, "PRAGMA table_info(episodes)")]
    rows = fetch_all(src, f"SELECT {', '.join(cols)} FROM episodes")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            # ключ по uuid (уникален в твоей схеме)
            if not data.get("uuid"):
                # fallback по (title_id, episode_number) если вдруг uuid пустой
                ex = fetch_one(dst,
                               "SELECT uuid FROM episodes WHERE title_id=? AND episode_number=?",
                               (data.get("title_id"), data.get("episode_number")))
                if ex: data["uuid"] = ex["uuid"]
            op = upsert_generic(cur, "episodes", ["uuid"], data,
                                overwrite_cols=set(cols) - {"uuid"})
            stats["episodes"][op] += 1

def merge_torrents(src, dst, stats):
    cols = [c[1] for c in fetch_all(src, "PRAGMA table_info(torrents)")]
    rows = fetch_all(src, f"SELECT {', '.join(cols)} FROM torrents")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            # ключ по hash; если пуст — строим резервный ключ
            h = data.get("hash")
            if not h:
                ex = fetch_one(dst, """
                    SELECT hash FROM torrents
                    WHERE title_id=? AND COALESCE(quality,'')=COALESCE(?, '') AND COALESCE(encoder,'')=COALESCE(?, '')
                      AND COALESCE(range_first,-1)=COALESCE(?, -1) AND COALESCE(range_last,-1)=COALESCE(?, -1)
                      AND COALESCE(total_size,-1)=COALESCE(?, -1)
                """, (data.get("title_id"), data.get("quality"), data.get("encoder"),
                      data.get("range_first"), data.get("range_last"), data.get("total_size")))
                if ex: data["hash"] = ex["hash"]
            op = upsert_generic(cur, "torrents", ["hash"], data,
                                overwrite_cols=set(cols) - {"hash"})
            stats["torrents"][op] += 1

def merge_posters(src, dst, stats):
    # не трогаем, если постер по такому hash_value уже есть
    rows = fetch_all(src, "SELECT poster_id, title_id, poster_blob, hash_value, last_updated FROM posters")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            if not data.get("hash_value"):
                # нет хэша — fallback по (title_id, poster_id) нельзя — переносим как новый
                op = upsert_generic(cur, "posters", ["poster_id"], data,
                                    overwrite_cols={"title_id","poster_blob","hash_value","last_updated"})
            else:
                ex = fetch_one(dst, "SELECT poster_id FROM posters WHERE hash_value=?", (data["hash_value"],))
                if ex:
                    # считаем, что файл идентичен — метаданные можем «освежить»
                    op = upsert_generic(cur, "posters", ["poster_id"], {
                        "poster_id": ex["poster_id"],
                        "title_id": data["title_id"],
                        "poster_blob": data["poster_blob"],  # если хочешь — можешь НЕ обновлять blob
                        "hash_value": data["hash_value"],
                        "last_updated": data["last_updated"],
                    }, overwrite_cols={"title_id","poster_blob","hash_value","last_updated"})
                else:
                    op = upsert_generic(cur, "posters", ["poster_id"], data,
                                        overwrite_cols={"title_id","poster_blob","hash_value","last_updated"})
            stats["posters"][op] += 1

def ensure_franchise_in_dst(dst, title_id, franchise_id_str, franchise_name, last_updated):
    # Franchise в твоей схеме: id (PK autoinc), title_id, franchise_id (TEXT), franchise_name
    ex = fetch_one(dst, "SELECT id FROM franchises WHERE title_id=? AND franchise_id=?",
                   (title_id, franchise_id_str))
    if ex:
        return ex["id"]
    cur = dst.cursor()
    cur.execute("INSERT INTO franchises (title_id, franchise_id, franchise_name, last_updated) VALUES (?,?,?,?)",
                (title_id, franchise_id_str, franchise_name, last_updated))
    return cur.lastrowid

def merge_franchises(src, dst, stats):
    # переносим/освежаем Franchise по (title_id, franchise_id)
    rows = fetch_all(src, "SELECT id, title_id, franchise_id, franchise_name, last_updated FROM franchises")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            ex = fetch_one(dst, "SELECT id FROM franchises WHERE title_id=? AND franchise_id=?",
                           (data["title_id"], data["franchise_id"]))
            if ex:
                op = upsert_generic(cur, "franchises", ["id"], {
                    "id": ex["id"],
                    "title_id": data["title_id"],
                    "franchise_id": data["franchise_id"],
                    "franchise_name": data["franchise_name"],
                    "last_updated": data["last_updated"],
                }, overwrite_cols={"title_id","franchise_id","franchise_name","last_updated"})
            else:
                op = upsert_generic(cur, "franchises", ["id"], data,
                                    overwrite_cols={"title_id","franchise_id","franchise_name","last_updated"})
            stats["franchises"][op] += 1

def merge_franchise_releases(src, dst, stats):
    # нам надо сопоставить FK franchise_id (int) через (title_id, franchise_id TEXT)
    rows = fetch_all(src, """SELECT fr.id, fr.franchise_id, fr.title_id, fr.code, fr.ordinal,
                                     fr.name_ru, fr.name_en, fr.name_alternative, fr.last_updated,
                                     f.title_id AS f_title_id, f.franchise_id AS f_fr_id, f.franchise_name
                              FROM franchise_releases fr
                              JOIN franchises f ON f.id = fr.franchise_id
                           """)
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            dst_fr_id = ensure_franchise_in_dst(dst, data["f_title_id"], data["f_fr_id"], data["franchise_name"], data["last_updated"])
            # устойчивый ключ: (dst_fr_id, title_id, code, COALESCE(ordinal,NULL))
            ex = fetch_one(dst, """
                SELECT id FROM franchise_releases
                 WHERE franchise_id=? AND title_id=? AND code=? AND COALESCE(ordinal, -1)=COALESCE(?, -1)
            """, (dst_fr_id, data["title_id"], data["code"], data["ordinal"]))
            payload = {
                "id": ex["id"] if ex else data["id"],
                "franchise_id": dst_fr_id,
                "title_id": data["title_id"],
                "code": data["code"],
                "ordinal": data["ordinal"],
                "name_ru": data["name_ru"],
                "name_en": data["name_en"],
                "name_alternative": data["name_alternative"],
                "last_updated": data["last_updated"],
            }
            op = upsert_generic(cur, "franchise_releases", ["id"], payload,
                                overwrite_cols={"franchise_id","title_id","code","ordinal",
                                                "name_ru","name_en","name_alternative","last_updated"})
            stats["franchise_releases"][op] += 1

def merge_title_genre_relations(src, dst, stats):
    # для каждой связи: матчим genre_id через name
    rows = fetch_all(src, """
        SELECT tgr.title_id, g.name as genre_name, tgr.last_updated
          FROM title_genre_relation tgr
          JOIN genres g ON g.genre_id = tgr.genre_id
    """)
    with dst:
        cur = dst.cursor()
        for r in rows:
            title_id = r["title_id"]; genre_name = r["genre_name"]
            g = fetch_one(dst, "SELECT genre_id FROM genres WHERE name=?", (genre_name,))
            if not g:
                # если жанра ещё нет — создадим
                cur.execute("INSERT INTO genres (name, last_updated) VALUES (?, ?)", (genre_name, r["last_updated"]))
                genre_id = cur.lastrowid
            else:
                genre_id = g["genre_id"]
            ex = fetch_one(dst, "SELECT id FROM title_genre_relation WHERE title_id=? AND genre_id=?",
                           (title_id, genre_id))
            if ex:
                op = upsert_generic(cur, "title_genre_relation", ["id"], {
                    "id": ex["id"],
                    "title_id": title_id,
                    "genre_id": genre_id,
                    "last_updated": r["last_updated"],
                }, overwrite_cols={"title_id","genre_id","last_updated"})
            else:
                op = upsert_generic(cur, "title_genre_relation", ["id"], {
                    "id": None, "title_id": title_id, "genre_id": genre_id, "last_updated": r["last_updated"]
                }, overwrite_cols={"title_id","genre_id","last_updated"})
            stats["title_genre_relation"][op] += 1

def merge_title_team_relations(src, dst, stats):
    rows = fetch_all(src, """
        SELECT ttr.title_id, tm.name AS tm_name, tm.role AS tm_role, ttr.last_updated
          FROM title_team_relation ttr
          JOIN team_members tm ON tm.id = ttr.team_member_id
    """)
    with dst:
        cur = dst.cursor()
        for r in rows:
            tm = fetch_one(dst, "SELECT id FROM team_members WHERE name=? AND role=?", (r["tm_name"], r["tm_role"]))
            if not tm:
                cur.execute("INSERT INTO team_members (name, role, last_updated) VALUES (?,?,?)",
                            (r["tm_name"], r["tm_role"], r["last_updated"]))
                tm_id = cur.lastrowid
            else:
                tm_id = tm["id"]
            ex = fetch_one(dst, "SELECT id FROM title_team_relation WHERE title_id=? AND team_member_id=?",
                           (r["title_id"], tm_id))
            payload = {"id": ex["id"] if ex else None,
                       "title_id": r["title_id"], "team_member_id": tm_id, "last_updated": r["last_updated"]}
            op = upsert_generic(cur, "title_team_relation", ["id"], payload,
                                overwrite_cols={"title_id","team_member_id","last_updated"})
            stats["title_team_relation"][op] += 1

def merge_ratings(src, dst, stats):
    rows = fetch_all(src, "SELECT rating_id, title_id, rating_name, rating_value, last_updated FROM ratings")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            ex = fetch_one(dst, "SELECT rating_id FROM ratings WHERE title_id=? AND rating_name=?",
                           (data["title_id"], data["rating_name"]))
            payload = {
                "rating_id": ex["rating_id"] if ex else data["rating_id"],
                "title_id": data["title_id"],
                "rating_name": data["rating_name"],
                "rating_value": data["rating_value"],
                "last_updated": data["last_updated"],
            }
            op = upsert_generic(cur, "ratings", ["rating_id"], payload,
                                overwrite_cols={"title_id","rating_name","rating_value","last_updated"})
            stats["ratings"][op] += 1

def merge_history(src, dst, stats):
    # безопасный мёрдж: OR/MAX/SUM
    rows = fetch_all(src, """SELECT id, user_id, title_id, episode_id, torrent_id,
                                    is_watched, last_watched_at, previous_watched_at, watch_change_count,
                                    is_download, last_download_at, previous_download_at, download_change_count,
                                    need_to_see
                               FROM history""")
    with dst:
        cur = dst.cursor()
        for r in rows:
            d = dict(r)
            key = (d["user_id"], d["title_id"], d["episode_id"], d["torrent_id"])
            ex = fetch_one(dst, """SELECT id, is_watched, last_watched_at, previous_watched_at, watch_change_count,
                                          is_download, last_download_at, previous_download_at, download_change_count,
                                          need_to_see
                                     FROM history
                                    WHERE user_id=? AND title_id=? AND COALESCE(episode_id,-1)=COALESCE(?, -1)
                                      AND COALESCE(torrent_id,-1)=COALESCE(?, -1)""", key)
            if not ex:
                # как есть
                op = upsert_generic(cur, "history", ["id"], d, overwrite_cols=set(d.keys())-{"id"})
                stats["history"][op] += 1
                continue

            ex = dict(ex)
            # OR/MAX/SUM
            payload = {
                "id": ex["id"],
                "user_id": d["user_id"],
                "title_id": d["title_id"],
                "episode_id": d["episode_id"],
                "torrent_id": d["torrent_id"],
                "is_watched": int(bool(ex["is_watched"]) or bool(d["is_watched"])),
                "last_watched_at": max(ex["last_watched_at"] or 0, d["last_watched_at"] or 0),
                "previous_watched_at": ex["previous_watched_at"] or d["previous_watched_at"],
                "watch_change_count": (ex["watch_change_count"] or 0) + (d["watch_change_count"] or 0),
                "is_download": int(bool(ex["is_download"]) or bool(d["is_download"])),
                "last_download_at": max(ex["last_download_at"] or 0, d["last_download_at"] or 0),
                "previous_download_at": ex["previous_download_at"] or d["previous_download_at"],
                "download_change_count": (ex["download_change_count"] or 0) + (d["download_change_count"] or 0),
                "need_to_see": int(bool(ex["need_to_see"]) or bool(d["need_to_see"])),
            }
            op = upsert_generic(cur, "history", ["id"], payload, overwrite_cols=set(payload.keys())-{"id"})
            stats["history"][op] += 1

def ensure_table_stats(stats, name):
    if name not in stats:
        stats[name] = {"insert":0, "update":0, "skip":0}

def run_merge(src_path, dst_path, dry_run=False):
    with closing(open_db(src_path)) as src, closing(open_db(dst_path)) as dst:
        # sanity
        if src_path == dst_path:
            raise SystemExit("source и destination совпадают")
        stats = {}
        for t in ["days_of_week","genres","team_members","titles","production_studios","schedule",
                  "episodes","torrents","posters","franchises","franchise_releases",
                  "title_genre_relation","title_team_relation","ratings","history"]:
            ensure_table_stats(stats, t)

        # порядки важны (FK!)
        merge_days_of_week(src, dst, stats)
        merge_genres(src, dst, stats)
        merge_team_members(src, dst, stats)

        merge_titles(src, dst, stats)
        merge_production_studio(src, dst, stats)
        merge_schedule(src, dst, stats)

        merge_episodes(src, dst, stats)
        merge_torrents(src, dst, stats)
        merge_posters(src, dst, stats)

        merge_franchises(src, dst, stats)
        merge_franchise_releases(src, dst, stats)

        merge_title_genre_relations(src, dst, stats)
        merge_title_team_relations(src, dst, stats)

        merge_ratings(src, dst, stats)
        merge_history(src, dst, stats)

        if dry_run:
            dst.rollback()
        else:
            dst.commit()

        # вывод сводки
        print("\n=== MERGE SUMMARY (source → dest) ===")
        for t, s in stats.items():
            print(f"{t:22s}  inserted: {s['insert']:6d}  updated: {s['update']:6d}  skipped: {s['skip']:6d}")
        if dry_run:
            print("\nNOTE: --dry-run был включён, изменения не записаны.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Merge two SQLite DBs (source → destination).")
    ap.add_argument("source_db")
    ap.add_argument("destination_db")
    ap.add_argument("--dry-run", action="store_true", help="Не писать в destination, только посчитать.")
    args = ap.parse_args()
    try:
        run_merge(args.source_db, args.destination_db, dry_run=args.dry_run)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
