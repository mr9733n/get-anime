# backfill_ranges.py
import os
import sqlite3, re

base_dir = os.path.dirname(os.path.abspath(__file__))
db_dir = os.path.join(base_dir, 'db')
db_path = os.path.join(db_dir, 'anime_player.db')

# dev
# db = r"F:\9834758345hf7A\Anime4.1\get-anime\db\anime_player.db"
# prod
db = r"F:\9834758345hf7A\Anime4.1\get-anime\dist\AnimePlayer\db\anime_player.db"

cn = sqlite3.connect(db)
cn.row_factory = sqlite3.Row
cur = cn.cursor()

def parse_res(row):
    for src in (row["resolution"] or "", row["quality"] or "", row["label"] or "", row["filename"] or ""):
        m = re.search(r'(\d{3,4})p', src, re.I)
        if m: return f"{m.group(1)}p"
    return None

def parse_range(rng):
    if not rng: return None, None
    m = re.search(r'(\d+)\s*[-–—]\s*(\d+)', rng)
    if m: return int(m.group(1)), int(m.group(2))
    m1 = re.fullmatch(r'\s*(\d+)\s*', rng)
    if m1:
        v = int(m1.group(1));
        return v, v
    return None, None

rows = cur.execute("SELECT torrent_id, resolution, quality, label, filename, episodes_range FROM torrents").fetchall()
upd = []
for r in rows:
    res = r["resolution"] or parse_res(r)
    rf, rl = parse_range(r["episodes_range"])
    if (r["resolution"] or None) != (res or None) or rf is not None or rl is not None:
        upd.append((res, rf, rl, r["torrent_id"]))

cur.executemany(
    "UPDATE torrents SET resolution = COALESCE(?, resolution), range_first = COALESCE(?, range_first), range_last = COALESCE(?, range_last) WHERE torrent_id = ?",
    upd
)
cn.commit()
cn.close()
print(f"Backfilled {len(upd)} rows")
