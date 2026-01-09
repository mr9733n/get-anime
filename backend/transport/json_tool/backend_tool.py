from __future__ import annotations

import argparse
import json
import sys

from backend.bootstrap.standalone import build_backend
from backend.transport.json_tool.protocol import parse_request, ok, fail
from backend.transport.json_tool.serializers import to_jsonable
from backend.transport.json_tool.handlers import HANDLERS


def _read_stdin_json() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Path to sqlite db file")
    parser.add_argument("--playlists-dir", default="playlists", help="Where to write generated m3u")
    args = parser.parse_args()

    backend = build_backend(db_path=args.db, playlists_dir=args.playlists_dir)

    try:
        payload = _read_stdin_json()
        req = parse_request(payload)

        handler = HANDLERS.get(req.op)
        if not handler:
            out = fail(f"Unknown op: {req.op}")
        else:
            out = handler(backend, req.params)

    except Exception as e:
        out = fail(str(e))

    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
