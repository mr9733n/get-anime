#!/usr/bin/env python3
from contextlib import closing
import argparse, sqlite3, time, sys


NOW = int(time.time())

def open_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, check_same_thread=False)
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

def ensure_franchise_in_dst(src, dst, title_id, franchise_id_str, franchise_name, last_updated, on_event=None):
    # гарантируем, что titles есть (иначе FK упрётся)
    try:
        ensure_title_in_dst(src, dst, int(title_id), on_event=on_event)
    except RuntimeError:
        # в источнике нет такого title — пусть вызывающий решит, что делать
        raise

    ex = fetch_one(dst, "SELECT id FROM franchises WHERE title_id=? AND franchise_id=?",
                   (title_id, franchise_id_str))
    if ex:
        return ex["id"]
    cur = dst.cursor()
    cur.execute("INSERT INTO franchises (title_id, franchise_id, franchise_name, last_updated) VALUES (?,?,?,?)",
                (title_id, franchise_id_str, franchise_name, last_updated))
    if on_event: on_event("franchises", f"insert:{title_id}/{franchise_id_str}")
    return cur.lastrowid

def ensure_title_in_dst(src, dst, title_id: int, on_event=None):
    if fetch_one(dst, "SELECT 1 FROM titles WHERE title_id=?", (title_id,)):
        return
    row = fetch_one(src, "SELECT * FROM titles WHERE title_id=?", (title_id,))
    if not row:
        raise RuntimeError(f"source missing titles({title_id}) required by child")
    cols = list(row.keys())
    upsert_generic(dst.cursor(), "titles", ["title_id"], dict(row),
                   overwrite_cols=set(cols)-{"last_updated"}, on_event=on_event)
    if on_event: on_event("titles", f"ensure:{title_id}")

def ensure_table_stats(stats, name):
    if name not in stats:
        stats[name] = {"insert":0, "update":0, "skip":0}

def resolve_dst_episode_id_by_uuid(dst, episode_uuid: str):
    row = fetch_one(dst, "SELECT episode_id FROM episodes WHERE uuid=?", (episode_uuid,))
    return row["episode_id"] if row else None

def resolve_dst_episode_id_by_src_id_via_uuid(src, dst, src_episode_id: int):
    # src id -> src uuid -> dst id
    row = fetch_one(src, "SELECT uuid FROM episodes WHERE episode_id=?", (src_episode_id,))
    if not row or not row["uuid"]:
        return None
    return resolve_dst_episode_id_by_uuid(dst, row["uuid"])

def resolve_dst_torrent_id_by_hash(dst, h: str):
    row = fetch_one(dst, "SELECT torrent_id FROM torrents WHERE hash=?", (h,))
    return row["torrent_id"] if row else None

def fk_violations(con, table: str):
    # PRAGMA foreign_key_check возвращает: (table, rowid, parent, fkid)
    try:
        rows = fetch_all(con, f"PRAGMA foreign_key_check({table})")
        return [tuple(r) for r in rows]
    except Exception:
        return []

def raise_fk_error(con, table: str, op: str, pk_cols, row_src: dict, inner: Exception):
    viol = fk_violations(con, table)
    # вытащим значение PK для дебага
    pk_tuple = {c: row_src.get(c) for c in pk_cols}
    msg = [
        f"FK failed on {table} during {op}",
        f"PK={pk_tuple}",
        f"error={inner!r}",
    ]
    if viol:
        # покажем до 5 нарушений, чтобы не зашумлять
        msg.append("foreign_key_check (first rows):")
        for v in viol[:5]:
            # (child_table, child_rowid, parent_table, fkid)
            msg.append(f"  -> {v}")
    raise RuntimeError("\n".join(msg)) from inner

def upsert_generic(cur_dst, table, pk_cols, row_src: dict,
                   overwrite_cols=None, fill_only_cols=None, set_cols=None,
                   on_event=None):
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
        try:
            cur_dst.execute(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
                vals
            )
        except sqlite3.IntegrityError as e:
            raise_fk_error(cur_dst.connection, table, "INSERT", pk_cols, row_src, e)
        if on_event: on_event(table, "insert")
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
        try:
            cur_dst.execute(f"UPDATE {table} SET {set_clause} WHERE {where}", args)
        except sqlite3.IntegrityError as e:
            raise_fk_error(cur_dst.connection, table, "UPDATE", pk_cols, row_src, e)
        if on_event: on_event(table, "update")
        return "update"
    if on_event: on_event(table, "skip")
    return "skip"

def merge_days_of_week(src, dst, stats, on_event=None):
    rows = fetch_all(src, "SELECT day_of_week, day_name FROM days_of_week")
    with dst:
        cur = dst.cursor()
        for r in rows:
            op = upsert_generic(cur, "days_of_week", ["day_of_week"], dict(r),
                                overwrite_cols={"day_name"}, on_event=on_event)
            stats["days_of_week"][op] += 1

def merge_genres(src, dst, stats, on_event=None):
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
                }, overwrite_cols={"name", "last_updated"}, on_event=on_event)
                stats["genres"][op] += 1
            else:
                # вставляем как есть: id может быть своим
                op = upsert_generic(cur, "genres", ["genre_id"], data, overwrite_cols={"name", "last_updated"}, on_event=on_event)
                stats["genres"][op] += 1

def merge_team_members(src, dst, stats, on_event=None):
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
                }, overwrite_cols={"name", "role", "last_updated"}, on_event=on_event)
            else:
                op = upsert_generic(cur, "team_members", ["id"], data, overwrite_cols={"name","role","last_updated"}, on_event=on_event)
            stats["team_members"][op] += 1

def merge_titles(src, dst, stats, on_event=None):
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
            op = upsert_generic(cur, "titles", ["title_id"], data, overwrite_cols=set(cols) - {"last_updated"}, on_event=on_event)
            stats["titles"][op] += 1

def merge_production_studio(src, dst, stats, on_event=None):
    if not fetch_one(src, "SELECT name FROM sqlite_master WHERE type='table' AND name='production_studios'"):
        return
    rows = fetch_all(src, "SELECT title_id, name, last_updated FROM production_studios")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            op = upsert_generic(cur, "production_studios", ["title_id"], data, overwrite_cols={"name","last_updated"}, on_event=on_event)
            stats["production_studios"][op] += 1

def merge_schedule(src, dst, stats, on_event=None):
    rows = fetch_all(src, "SELECT day_of_week, title_id, last_updated FROM schedule")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            ensure_title_in_dst(src, dst, int(data["title_id"]), on_event=on_event)
            op = upsert_generic(cur, "schedule", ["day_of_week","title_id"], data,
                                overwrite_cols={"last_updated"}, on_event=on_event)
            stats["schedule"][op] += 1

def merge_episodes(src, dst, stats, on_event=None):
    cols = [c[1] for c in fetch_all(src, "PRAGMA table_info(episodes)")]
    rows = fetch_all(src, f"SELECT {', '.join(cols)} FROM episodes")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            if not data.get("uuid"):
                # fallback, если вдруг uuid пуст:
                ex = fetch_one(dst, "SELECT uuid FROM episodes WHERE title_id=? AND episode_number=?",
                               (data.get("title_id"), data.get("episode_number")))
                if ex: data["uuid"] = ex["uuid"]

            # не допускаем изменения episode_id
            overwrite = set(cols) - {"uuid", "episode_id"}
            exists = fetch_one(dst, "SELECT 1 FROM episodes WHERE uuid=?", (data.get("uuid"),))
            payload = dict(data)
            payload.pop("episode_id", None)  # и для INSERT, и для UPDATE
            op = upsert_generic(cur, "episodes", ["uuid"], payload,
                                overwrite_cols=overwrite,
                                # доп. гарантия: на UPDATE зафиксировать episode_id прежним (если вдруг кто-то передаст)
                                set_cols={"episode_id": (lambda dst_val, src_val: dst_val)},
                                on_event=on_event)
            stats["episodes"][op] += 1

def merge_torrents(src, dst, stats, on_event=None):
    cols = [c[1] for c in fetch_all(src, "PRAGMA table_info(torrents)")]
    rows = fetch_all(src, f"SELECT {', '.join(cols)} FROM torrents")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            h = data.get("hash")
            if not h:
                # если вдруг нет hash — можно сгенерить из набора полей (аккуратно),
                # но лучше такие записи пропускать:
                if on_event: on_event("torrents", "skip:no-hash")
                continue

            ensure_title_in_dst(src, dst, int(data.get("title_id") or 0), on_event=on_event)

            overwrite = set(cols) - {"hash", "torrent_id"}
            payload = dict(data)
            payload.pop("torrent_id", None)
            op = upsert_generic(cur, "torrents", ["hash"], payload,
                                overwrite_cols=overwrite,
                                set_cols={"torrent_id": (lambda dst_val, src_val: dst_val)},
                                on_event=on_event)
            stats["torrents"][op] += 1

def merge_posters(src, dst, stats, on_event=None, skip_flag=False):
    """
    Политика:
      - Если у постера есть hash_value: ключом считаем (title_id, hash_value).
      - Если такого постера уже нет — вставляем БЕЗ poster_id (пусть БД выдаст PK).
      - Если hash_value пуст — пытаемся обновить по poster_id; если в dst такого нет — мягко вставляем без poster_id.
      - Родителя (titles) гарантируем через ensure_title_in_dst; если в src нет такого title — пропускаем (щадяще).
    """
    rows = fetch_all(src, "SELECT poster_id, title_id, poster_blob, hash_value, last_updated FROM posters")
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            title_id = data.get("title_id")
            hash_value = data.get("hash_value")

            if not title_id:
                if on_event: on_event("posters", "skip:no-title_id")
                continue

            if not hash_value and skip_flag: continue


            # 1) гарантируем, что titles есть; если в src его нет — щадяще пропускаем
            try:
                ensure_title_in_dst(src, dst, int(title_id), on_event=on_event)
            except RuntimeError:
                if on_event: on_event("posters", f"skip_orphan_title:{title_id}")
                continue

            hv = data.get("hash_value")

            if hv:
                # 2) дедуп по (title_id, hash_value)
                ex = fetch_one(dst, "SELECT poster_id FROM posters WHERE title_id=? AND hash_value=?",
                               (title_id, hv))
                if ex:
                    # освежаем мета/контент по найденному poster_id
                    payload = {
                        "poster_id": ex["poster_id"],
                        "title_id": title_id,
                        "poster_blob": data["poster_blob"],
                        "hash_value": hv,
                        "last_updated": data["last_updated"],
                    }
                    op = upsert_generic(cur, "posters", ["poster_id"], payload,
                                        overwrite_cols={"title_id","poster_blob","hash_value","last_updated"},
                                        on_event=on_event)
                else:
                    # нет такого файла у этого тайтла — мягкая вставка без poster_id (чтобы не конфликтовать PK)
                    try:
                        cur.execute(
                            "INSERT INTO posters (title_id, poster_blob, hash_value, last_updated) VALUES (?,?,?,?)",
                            (title_id, data["poster_blob"], hv, data["last_updated"])
                        )
                        op = "insert"
                        if on_event: on_event("posters", "insert")
                    except sqlite3.IntegrityError as e:
                        # если вдруг (редко) FK/UNIQUE — поднимем понятную ошибку
                        raise_fk_error(dst, "posters", "INSERT", ["poster_id"], data, e)
            else:
                # 3) нет хэша — сначала пробуем обновить, если poster_id совпал,
                #    иначе мягко вставим без poster_id
                pid = data.get("poster_id")
                if pid and fetch_one(dst, "SELECT 1 FROM posters WHERE poster_id=?", (pid,)):
                    payload = {
                        "poster_id": pid,
                        "title_id": title_id,
                        "poster_blob": data["poster_blob"],
                        "hash_value": None,
                        "last_updated": data["last_updated"],
                    }
                    op = upsert_generic(cur, "posters", ["poster_id"], payload,
                                        overwrite_cols={"title_id","poster_blob","hash_value","last_updated"},
                                        on_event=on_event)
                else:
                    try:
                        cur.execute(
                            "INSERT INTO posters (title_id, poster_blob, hash_value, last_updated) VALUES (?,?,?,?)",
                            (title_id, data["poster_blob"], None, data["last_updated"])
                        )
                        op = "insert"
                        if on_event: on_event("posters", "insert")
                    except sqlite3.IntegrityError as e:
                        raise_fk_error(dst, "posters", "INSERT", ["poster_id"], data, e)

            stats["posters"][op] += 1

def merge_franchises(src, dst, stats, on_event=None):
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
                }, overwrite_cols={"title_id","franchise_id","franchise_name","last_updated"},
                                    on_event=on_event)
            else:
                op = upsert_generic(cur, "franchises", ["id"], data,
                                    overwrite_cols={"title_id","franchise_id","franchise_name","last_updated"},
                                    on_event=on_event)
            stats["franchises"][op] += 1

def merge_franchise_releases(src, dst, stats, on_event=None):
    """
    Политика:
      - FK: гарантируем title и franchise перед вставкой (если title отсутствует в src — пропускаем релиз).
      - Дедуп/апдейт по естественному ключу:
           (franchise_id, title_id, COALESCE(code,''), COALESCE(ordinal,-1))
      - id не переносим на INSERT (пусть БД задаёт сама).
    """
    rows = fetch_all(src, """
        SELECT fr.id, fr.franchise_id AS fr_int_id, fr.title_id, fr.code, fr.ordinal,
               fr.name_ru, fr.name_en, fr.name_alternative, fr.last_updated,
               f.title_id AS f_title_id, f.franchise_id AS f_fr_id, f.franchise_name
        FROM franchise_releases fr
        JOIN franchises f ON f.id = fr.franchise_id
    """)
    with dst:
        cur = dst.cursor()
        for r in rows:
            data = dict(r)
            title_id = data["title_id"]

            # 1) title + franchise в dst (title обязателен в src, иначе пропускаем)
            try:
                dst_fr_id = ensure_franchise_in_dst(
                    src, dst,
                    data["f_title_id"],           # у франшизы свой title_id (обычно тот же)
                    data["f_fr_id"],
                    data["franchise_name"],
                    data["last_updated"],
                    on_event=on_event
                )
            except RuntimeError:
                # нет title в src — щадяще пропускаем релиз
                if on_event: on_event("franchise_releases", f"skip_orphan_title:{title_id}")
                continue

            try:
                ensure_title_in_dst(src, dst, int(title_id), on_event=on_event)
            except RuntimeError:
                if on_event: on_event("franchise_releases", f"skip_orphan_title:{title_id}")
                stats["franchise_releases"]["skip"] += 1
                continue
            # 2) ищем по естественному ключу в dst
            ex = fetch_one(dst, """
                SELECT id FROM franchise_releases
                 WHERE franchise_id=? AND title_id=? AND COALESCE(code,'')=COALESCE(?, '')
                   AND COALESCE(ordinal, -1)=COALESCE(?, -1)
            """, (dst_fr_id, title_id, data["code"], data["ordinal"]))

            if ex:
                # UPDATE по id найденной строки
                payload = {
                    "id": ex["id"],
                    "franchise_id": dst_fr_id,
                    "title_id": title_id,
                    "code": data["code"],
                    "ordinal": data["ordinal"],
                    "name_ru": data["name_ru"],
                    "name_en": data["name_en"],
                    "name_alternative": data["name_alternative"],
                    "last_updated": data["last_updated"],
                }
                op = upsert_generic(cur, "franchise_releases", ["id"], payload,
                                    overwrite_cols={"franchise_id","title_id","code","ordinal",
                                                    "name_ru","name_en","name_alternative","last_updated"},
                                    on_event=on_event)
            else:
                # INSERT без переноса id
                try:
                    cur.execute("""
                        INSERT INTO franchise_releases
                          (franchise_id, title_id, code, ordinal,
                           name_ru, name_en, name_alternative, last_updated)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (dst_fr_id, title_id, data["code"], data["ordinal"],
                          data["name_ru"], data["name_en"], data["name_alternative"], data["last_updated"]))
                    op = "insert"
                    if on_event: on_event("franchise_releases", "insert")
                except sqlite3.IntegrityError as e:
                    raise_fk_error(dst, "franchise_releases", "INSERT",
                                   ["franchise_id","title_id","code","ordinal"], data, e)

            stats["franchise_releases"][op] += 1

def merge_title_genre_relations(src, dst, stats, on_event=None):
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
                }, overwrite_cols={"title_id","genre_id","last_updated"},
                                    on_event=on_event)
            else:
                op = upsert_generic(cur, "title_genre_relation", ["id"], {
                    "id": None, "title_id": title_id, "genre_id": genre_id, "last_updated": r["last_updated"]
                }, overwrite_cols={"title_id","genre_id","last_updated"},
                                    on_event=on_event)
            stats["title_genre_relation"][op] += 1

def merge_title_team_relations(src, dst, stats, on_event=None):
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
                                overwrite_cols={"title_id","team_member_id","last_updated"},
                                on_event=on_event)
            stats["title_team_relation"][op] += 1

def merge_ratings(src, dst, stats, on_event=None):
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
                                overwrite_cols={"title_id","rating_name","rating_value","last_updated"},
                                on_event=on_event)
            stats["ratings"][op] += 1

def merge_history(src, dst, stats, on_event=None):
    cols = [c[1] for c in fetch_all(src, "PRAGMA table_info(history)")]
    rows = fetch_all(src, f"SELECT {', '.join(cols)} FROM history")
    with dst:
        cur = dst.cursor()
        for r in rows:
            d = dict(r)

            # episode_id: src -> uuid -> dst
            if d.get("episode_id") is not None:
                new_ep = resolve_dst_episode_id_by_src_id_via_uuid(src, dst, d["episode_id"])
                if new_ep is not None:
                    d["episode_id"] = new_ep
                else:
                    # нет такого эпизода в dst — можно пропустить или занести как orphan
                    if on_event: on_event("history", f"skip_orphan_episode:{r.get('episode_id')}")
                    continue

            # torrent_id: чаще всего можно резолвить по hash (если хранится в history);
            # если в history нет hash — берём его из src.torrents по torrent_id
            if d.get("torrent_id") is not None:
                row = fetch_one(src, "SELECT hash FROM torrents WHERE torrent_id=?", (d["torrent_id"],))
                if row and row["hash"]:
                    new_tid = resolve_dst_torrent_id_by_hash(dst, row["hash"])
                    if new_tid is not None:
                        d["torrent_id"] = new_tid
                    else:
                        if on_event: on_event("history", f"skip_orphan_torrent:{d['torrent_id']}")
                        continue

            ex = fetch_one(dst, "SELECT 1 FROM history WHERE id=?", (d.get("id"),))
            if not ex:
                op = upsert_generic(cur, "history", ["id"], d,
                                    overwrite_cols=set(d.keys())-{"id"},
                                    on_event=on_event)
                stats["history"][op] += 1
                continue

            op = upsert_generic(cur, "history", ["id"], d,
                                overwrite_cols=set(d.keys())-{"id"},
                                on_event=on_event)
            stats["history"][op] += 1

def run_merge(
        src_path, dst_path,
        skip_posters_without_hash=False,
        skip_orphans=False,
        vacuum_optimize=False,
        dry_run=False,
        on_event=None,
        verbose=False):
    with closing(open_db(src_path)) as src, closing(open_db(dst_path)) as dst:
        dst.execute("PRAGMA foreign_keys = ON;")
        # если твоя версия SQLite поддерживает — отложит проверку до COMMIT:
        dst.execute("PRAGMA defer_foreign_keys = ON;")

        # sanity
        if src_path == dst_path:
            raise SystemExit("source и destination совпадают")
        stats = {}
        for t in ["days_of_week","genres","team_members","titles","production_studios","schedule",
                  "episodes","torrents","posters","franchises","franchise_releases",
                  "title_genre_relation","title_team_relation","ratings","history"]:
            ensure_table_stats(stats, t)

        orphans = []  # сюда собираем сирот

        def record_event(table, op):
            # внешний on_event + verbose — как раньше
            if on_event and verbose:
                on_event(table, op)
            # наши сироты
            if "skip_orphan" in op:
                key = None
                if ":" in op:
                    _, key = op.split(":", 1)
                orphans.append({
                    "table": table,
                    "op": op,
                    "key": key,
                })

        # def _noop_event(*args, **kwargs): pass
        # evt = on_event if verbose and on_event else _noop_event
        # порядки важны (FK!)
        merge_days_of_week(src, dst, stats, on_event=record_event)
        merge_genres(src, dst, stats, on_event=record_event)
        merge_team_members(src, dst, stats, on_event=record_event)

        merge_titles(src, dst, stats, on_event=record_event)
        merge_production_studio(src, dst, stats, on_event=record_event)
        merge_schedule(src, dst, stats, on_event=record_event)
        merge_episodes(src, dst, stats, on_event=record_event)
        merge_torrents(src, dst, stats, on_event=record_event)
        merge_posters(src, dst, stats, on_event=record_event, skip_flag=skip_posters_without_hash)
        merge_franchises(src, dst, stats, on_event=record_event)
        merge_franchise_releases(src, dst, stats, on_event=record_event)
        merge_title_genre_relations(src, dst, stats, on_event=record_event)
        merge_title_team_relations(src, dst, stats, on_event=record_event)
        merge_ratings(src, dst, stats, on_event=record_event)
        merge_history(src, dst, stats, on_event=record_event)

        violate = fetch_all(dst, "PRAGMA foreign_key_check")

        if skip_orphans:
            ...

        if dry_run:
            dst.rollback()
        else:
            dst.commit()
            if vacuum_optimize:
                dst.execute("PRAGMA optimize")
                dst.execute("VACUUM")
        return stats, violate, orphans


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Merge two SQLite DBs (source → destination).")
    ap.add_argument("source_db")
    ap.add_argument("destination_db")
    ap.add_argument("--dry-run", action="store_true", help="Не писать в destination, только посчитать.")
    ap.add_argument("--verbose", action="store_true", help="Подробный поток on_event (шумно).")
    args = ap.parse_args()
    try:
        stats, viol, orphans = run_merge(args.source_db, args.destination_db, dry_run=args.dry_run, verbose=args.verbose)
        # вывод сводки
        if viol:
        # вывести в лог/GUI список нарушений
            print("\n=== VIOLATION SUMMARY (source → dest) ===")
            head = viol[:10]
            print(f"{len(viol)} violations, first 10:\n{head}")
        print("\n=== MERGE SUMMARY (source → dest) ===")
        for t, s in stats.items():
            print(f"{t:22s}  inserted: {s['insert']:6d}  updated: {s['update']:6d}  skipped: {s['skip']:6d}")
        if orphans:
            print("\n=== ORPHANS SUMMARY ===")
            print(f"{len(orphans)} orphan rows (see GUI or future CSV export)")
        if args.dry_run:
            print("\nNOTE: --dry-run был включён, изменения не записаны.")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
