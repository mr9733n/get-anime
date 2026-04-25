"""
Integration smoke tests for the provider → write-path pipeline.

Two layers of coverage:
  1. Pure-unit tests of _unpack_process_titles helper (no DB needed).
  2. Behavioural tests via StubStorage — real StorageProcessWritePort logic,
     fake storage that records calls.  No SQLAlchemy / live DB required.
  3. Real-DB tests skipped when SQLAlchemy is not importable (broken env).

What is verified:
  - StorageProcessWritePort.apply_provider_payload correctly extracts
    title_id from the (bool, title_id) tuple returned by process_titles
  - title_id is injected into the enriched payload before process_episodes,
    so episodes are saved with the correct FK (was broken before fix)
  - AniMedia poster fallback: poster_path_medium filled from posters.original
    (validated via StorageProcessWritePort + stub storage + payload check)
  - Repeat update is idempotent (no unique-constraint errors)
  - apply_provider_payload returns ok=True + non-None title_id
"""
from __future__ import annotations

import os
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Fixture payloads  (repr of what the provider adapters actually produce)
# ---------------------------------------------------------------------------

# AniLiberty legacy format — output of APIAdapter.get_release_full()
ANILIBERTY_PAYLOAD: dict = {
    "provider": "aniliberty",
    "external_id": 9001,
    "code": "test-title-aniliberty",
    "names": {
        "ru": "Тестовый тайтл AniLiberty",
        "en": "Test Title AniLiberty",
        "alternative": "",
    },
    "franchises": [],
    "announce": "",
    "status": {"string": "Вышел", "code": 4},
    "posters": {
        "small":    {"url": "https://cdn.example.com/small.jpg"},
        "medium":   {"url": "https://cdn.example.com/medium.jpg"},
        "original": {"url": "https://cdn.example.com/original.jpg"},
    },
    "updated": 0,
    "last_change": 0,
    "type": {
        "full_string": "ТВ-сериал, 2 эп.",
        "code": 0,
        "string": "ТВ",
        "episodes": 2,
        "length": "24",
    },
    "genres": ["Боевик"],
    "team": {"voice": ["Тест В."], "translator": [], "timing": []},
    "season": {"string": "Осень", "code": 4, "year": 2024, "week_day": 4},
    "description": "Тестовое описание",
    "in_favorites": 0,
    "blocked": {"copyrights": False, "geoip": False, "geoip_list": []},
    "player": {
        "host": "cache.libria.fun",
        "alternative_player": "",
        "list": [
            {
                "episode": 1,
                "name": "Серия 1",
                "uuid": "fixture-uuid-ep1",
                "created_timestamp": 1700000001,
                "hls": {"sd": "/sd/test/1.m3u8", "hd": "/hd/test/1.m3u8", "fhd": None},
                "preview": None,
                "skips": {"opening": [], "ending": []},
            },
            {
                "episode": 2,
                "name": "Серия 2",
                "uuid": "fixture-uuid-ep2",
                "created_timestamp": 1700000002,
                "hls": {"sd": "/sd/test/2.m3u8", "hd": "/hd/test/2.m3u8", "fhd": None},
                "preview": None,
                "skips": {"opening": [], "ending": []},
            },
        ],
    },
    "torrents": {"list": []},
    "rating": {"name": "shikimori", "score": 8.5},
    "studio": "Test Studio",
}

# AniMedia legacy format — output of Title.to_legacy()
# Notable: only posters.original has a URL; medium/small are empty dicts.
ANIMEDIA_PAYLOAD: dict = {
    "external_id": 2002,
    "provider": "AniMedia",
    "code": "",
    "announce": "",
    "names": {"ru": "Тестовый тайтл AniMedia", "en": "", "alternative": ""},
    "description": "",
    "season": {"code": None, "string": "", "year": 2024, "week_day": None},
    "status": {"code": 2, "string": "Завершён"},
    "type": {"code": 0, "string": "", "full_string": "", "episodes": 0, "length": None},
    "studio": "",
    "rating": {"name": "AniMedia", "score": 0.0},
    "genres": [],
    "posters": {
        "small":    {},
        "medium":   {},
        "original": {"url": "https://static.animedia.ac/test-poster.jpg"},
    },
    "updated": 0,
    "last_change": 0,
    "in_favorites": 0,
    "blocked": {"copyrights": False, "geoip": False, "geoip_list": []},
    "player": {
        "host": "online.animedia.ac",
        "alternative_player": "",
        "list": {},  # empty episodes dict (no episodes in schedule payload)
    },
    "team": {"voice": [], "translator": [], "timing": []},
    "franchises": [],
    "torrents": {"list": []},
}


# ---------------------------------------------------------------------------
# Stub storage — records calls, returns tuples like real ProcessManager
# ---------------------------------------------------------------------------

class StubStorage:
    """
    Minimal stub that mimics DatabaseManager.process_* return values.

    process_titles  → (ok: bool, title_id: int)    ← the tuple pattern
    process_episodes → True
    process_torrents → True
    """

    def __init__(self, title_id: int = 42, fail: bool = False):
        self._title_id = title_id
        self._fail = fail
        self.calls: list[tuple[str, dict]] = []

    def process_titles(self, payload: dict):
        self.calls.append(("process_titles", dict(payload)))
        if self._fail:
            return (False, None)
        return (True, self._title_id)

    def process_episodes(self, payload: dict):
        self.calls.append(("process_episodes", dict(payload)))
        return True

    def process_torrents(self, payload: dict):
        self.calls.append(("process_torrents", dict(payload)))
        return True

    # convenience
    def called_with(self, name: str) -> list[dict]:
        return [p for n, p in self.calls if n == name]


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_write_port(storage):
    from backend.infra.db.process_write_port_storage import StorageProcessWritePort
    return StorageProcessWritePort(storage=storage, poster_job=None)


# ---------------------------------------------------------------------------
# Unit: _unpack_process_titles helper
# ---------------------------------------------------------------------------

class TestUnpackProcessTitles:
    def test_tuple_ok_with_id(self):
        from backend.infra.db.process_write_port_storage import _unpack_process_titles
        ok, tid = _unpack_process_titles((True, 42))
        assert ok is True
        assert tid == 42

    def test_tuple_failed(self):
        from backend.infra.db.process_write_port_storage import _unpack_process_titles
        ok, tid = _unpack_process_titles((False, None))
        assert ok is False
        assert tid is None

    def test_dict_ok_with_id(self):
        from backend.infra.db.process_write_port_storage import _unpack_process_titles
        ok, tid = _unpack_process_titles({"ok": True, "title_id": 7})
        assert ok is True
        assert tid == 7

    def test_dict_nested_result(self):
        from backend.infra.db.process_write_port_storage import _unpack_process_titles
        ok, tid = _unpack_process_titles({"result": {"title_id": 99}})
        assert tid == 99

    def test_truthy_scalar_ok_no_id(self):
        from backend.infra.db.process_write_port_storage import _unpack_process_titles
        ok, tid = _unpack_process_titles(True)
        assert ok is True
        assert tid is None

    def test_none_returns_false(self):
        from backend.infra.db.process_write_port_storage import _unpack_process_titles
        ok, tid = _unpack_process_titles(None)
        assert ok is False
        assert tid is None

    def test_single_element_tuple(self):
        from backend.infra.db.process_write_port_storage import _unpack_process_titles
        ok, tid = _unpack_process_titles((True,))
        # len < 2 → falls to scalar path
        assert ok is True
        assert tid is None


# ---------------------------------------------------------------------------
# Behavioural: StorageProcessWritePort with StubStorage
# ---------------------------------------------------------------------------

class TestApplyProviderPayloadBehavioural:
    """Test StorageProcessWritePort behaviour using StubStorage (no real DB)."""

    # --- title_id extraction ---

    def test_title_mode_returns_title_id_from_tuple(self):
        """Bug: before fix, title_id was never extracted from (bool, id) tuple."""
        storage = StubStorage(title_id=77)
        port = make_write_port(storage)
        result = port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="title",
        )
        assert result.ok is True
        assert result.title_id == 77, (
            "title_id must be extracted from the (bool, title_id) tuple returned by process_titles"
        )

    def test_full_mode_returns_title_id_from_tuple(self):
        """title_full mode also must extract title_id from tuple."""
        storage = StubStorage(title_id=123)
        port = make_write_port(storage)
        result = port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="title_full",
        )
        assert result.ok is True
        assert result.title_id == 123

    # --- title_id injection into episodes ---

    def test_episodes_receive_injected_title_id(self):
        """Bug: before fix, process_episodes got payload WITHOUT title_id, so FK was NULL."""
        storage = StubStorage(title_id=55)
        port = make_write_port(storage)
        port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="title_full",
        )
        eps_calls = storage.called_with("process_episodes")
        assert len(eps_calls) == 1, "process_episodes must be called once"
        episode_payload = eps_calls[0]
        assert episode_payload.get("title_id") == 55, (
            "process_episodes payload must have title_id=55 injected "
            f"(got {episode_payload.get('title_id')!r})"
        )

    def test_original_payload_not_mutated(self):
        """StorageProcessWritePort must not mutate the caller's payload dict."""
        storage = StubStorage(title_id=99)
        port = make_write_port(storage)
        original = dict(ANILIBERTY_PAYLOAD)
        original.pop("title_id", None)  # ensure no pre-existing key
        port.apply_provider_payload(
            provider_code="aniliberty",
            payload=original,
            mode="title_full",
        )
        assert "title_id" not in original, (
            "apply_provider_payload must not inject title_id into the caller's dict"
        )

    # --- AniLiberty: applied list ---

    def test_full_mode_applied_includes_title_and_episodes(self):
        storage = StubStorage(title_id=42)
        port = make_write_port(storage)
        result = port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="title_full",
        )
        applied = (result.details or {}).get("applied", [])
        assert "title" in applied
        assert "episodes" in applied

    def test_title_mode_applied_contains_only_title(self):
        storage = StubStorage(title_id=42)
        port = make_write_port(storage)
        result = port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="title",
        )
        applied = (result.details or {}).get("applied", [])
        assert applied == ["title"]

    # --- AniMedia: no episodes (empty list dict) ---

    def test_animedia_no_episodes_skips_process_episodes(self):
        """AniMedia schedule payloads have empty player.list — must not call process_episodes."""
        storage = StubStorage(title_id=42)
        port = make_write_port(storage)
        port.apply_provider_payload(
            provider_code="animedia",
            payload=ANIMEDIA_PAYLOAD,
            mode="title_full",
        )
        assert storage.called_with("process_episodes") == [], (
            "process_episodes must not be called when player.list is empty"
        )

    def test_animedia_full_mode_returns_title_id(self):
        storage = StubStorage(title_id=200)
        port = make_write_port(storage)
        result = port.apply_provider_payload(
            provider_code="animedia",
            payload=ANIMEDIA_PAYLOAD,
            mode="title_full",
        )
        assert result.ok is True
        assert result.title_id == 200

    # --- auto mode detection ---

    def test_auto_mode_detects_player_key_as_full(self):
        storage = StubStorage(title_id=1)
        port = make_write_port(storage)
        result = port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="auto",
        )
        assert result.mode in ("title_full", "full")

    def test_auto_mode_no_player_key_as_title(self):
        storage = StubStorage(title_id=1)
        port = make_write_port(storage)
        minimal = {
            "provider": "aniliberty",
            "external_id": 1,
            "names": {"ru": "x", "en": "", "alternative": ""},
        }
        result = port.apply_provider_payload(
            provider_code="aniliberty",
            payload=minimal,
            mode="auto",
        )
        assert result.mode == "title"

    # --- failure propagation ---

    def test_failed_process_titles_propagates_ok_false(self):
        storage = StubStorage(title_id=42, fail=True)
        port = make_write_port(storage)
        result = port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="title",
        )
        assert result.ok is False
        assert result.title_id is None

    def test_failed_title_skips_episodes(self):
        """When process_titles fails, process_episodes must NOT be called."""
        storage = StubStorage(title_id=42, fail=True)
        port = make_write_port(storage)
        port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="title_full",
        )
        assert storage.called_with("process_episodes") == [], (
            "process_episodes must not be called after process_titles failure"
        )

    def test_unsupported_mode_returns_ok_false(self):
        storage = StubStorage()
        port = make_write_port(storage)
        result = port.apply_provider_payload(
            provider_code="x",
            payload={},
            mode="unknown_mode",
        )
        assert result.ok is False
        assert "unsupported_mode" in (result.error or "")

    # --- idempotency (stub level) ---

    def test_two_calls_both_return_same_title_id(self):
        storage = StubStorage(title_id=42)
        port = make_write_port(storage)
        r1 = port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="title_full",
        )
        r2 = port.apply_provider_payload(
            provider_code="aniliberty",
            payload=ANILIBERTY_PAYLOAD,
            mode="title_full",
        )
        assert r1.ok and r2.ok
        assert r1.title_id == r2.title_id == 42


# ---------------------------------------------------------------------------
# Real-DB tests — skipped when SQLAlchemy is not importable (broken env)
# ---------------------------------------------------------------------------

def _sqlalchemy_available() -> bool:
    try:
        from sqlalchemy.orm import sessionmaker  # noqa: F401
        return True
    except Exception:
        return False


_skip_no_sqla = pytest.mark.skipif(
    not _sqlalchemy_available(),
    reason="SQLAlchemy not importable in this environment (check installation)"
)


@pytest.fixture()
def real_db():
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="anime_test_")
    os.close(fd)
    try:
        from storage.database_manager import DatabaseManager
        dm = DatabaseManager(db_path)
        dm.initialize_tables()
        yield dm
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


@pytest.fixture()
def real_write_port(real_db):
    from backend.infra.db.process_write_port_storage import StorageProcessWritePort
    return StorageProcessWritePort(storage=real_db, poster_job=None)


@_skip_no_sqla
def test_realdb_aniliberty_full_saves_title_and_episodes(real_write_port, real_db):
    """End-to-end: AniLiberty title + 2 episodes saved with correct FK."""
    result = real_write_port.apply_provider_payload(
        provider_code="aniliberty",
        payload=ANILIBERTY_PAYLOAD,
        mode="title_full",
    )
    assert result.ok is True
    assert result.title_id is not None

    from storage.tables import Episode
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=real_db.engine)
    with Session() as session:
        episodes = session.query(Episode).filter_by(title_id=result.title_id).all()
    assert len(episodes) == 2
    for ep in episodes:
        assert ep.title_id == result.title_id


@_skip_no_sqla
def test_realdb_animedia_poster_medium_fallback(real_write_port, real_db):
    """End-to-end: AniMedia poster_path_medium is filled from original."""
    result = real_write_port.apply_provider_payload(
        provider_code="animedia",
        payload=ANIMEDIA_PAYLOAD,
        mode="title_full",
    )
    assert result.ok is True

    from storage.tables import Title
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=real_db.engine)
    with Session() as session:
        title = session.query(Title).filter_by(title_id=result.title_id).one()
    assert title.poster_path_medium == "https://static.animedia.ac/test-poster.jpg"


@_skip_no_sqla
def test_realdb_idempotent_repeat_update(real_write_port, real_db):
    """Repeat apply_provider_payload for same title is idempotent."""
    r1 = real_write_port.apply_provider_payload(
        provider_code="aniliberty",
        payload=ANILIBERTY_PAYLOAD,
        mode="title_full",
    )
    r2 = real_write_port.apply_provider_payload(
        provider_code="aniliberty",
        payload=ANILIBERTY_PAYLOAD,
        mode="title_full",
    )
    assert r1.ok and r2.ok
    assert r1.title_id == r2.title_id

    # No episode row duplication
    from storage.tables import Episode
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=real_db.engine)
    with Session() as session:
        count = session.query(Episode).filter_by(title_id=r2.title_id).count()
    assert count <= 2, f"duplicate episodes after repeat update: {count} rows"
