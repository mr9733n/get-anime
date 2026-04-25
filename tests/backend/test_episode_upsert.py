"""
Unit tests for the episode processing / upsert pipeline.

Tests ProcessManager.process_episodes() using a MockSaveManager that
records every save_episode() call.  Verifies:
  - title_id from payload is passed to every episode
  - episode_number extracted from episode["episode"]
  - HLS fields correctly mapped from episode["hls"]
  - AniMedia dict-format player.list ({"1": {...}, "2": {...}}) is handled
  - AniLiberty list-format player.list ([{...}, {...}]) is handled
  - Episodes without "hls" key are skipped (e.g. Pending/unreleased episodes)
  - uuid forwarded correctly
  - created_timestamp: unix float → datetime, 0 default if missing
  - skips fields serialised to JSON strings
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# MockSaveManager — records save_episode calls
# ---------------------------------------------------------------------------

class MockSaveManager:
    def __init__(self):
        self.saved: list[dict] = []

    def save_episode(self, episode_data: dict) -> None:
        self.saved.append(dict(episode_data))


def make_process_manager() -> tuple:
    from storage.process import ProcessManager
    sm = MockSaveManager()
    pm = ProcessManager(sm)
    return pm, sm


# ---------------------------------------------------------------------------
# Fixture payloads
# ---------------------------------------------------------------------------

# AniLiberty: player.list is a Python list
ANILIBERTY_PLAYER = {
    "host": "cache.libria.fun",
    "list": [
        {
            "episode": 1,
            "name": "Серия 1",
            "uuid": "uuid-ep-1",
            "created_timestamp": 1700000001,
            "hls": {"sd": "/sd/1.m3u8", "hd": "/hd/1.m3u8", "fhd": "/fhd/1.m3u8"},
            "preview": "/preview/1.jpg",
            "skips": {"opening": [5, 90], "ending": [1350, 1440]},
        },
        {
            "episode": 2,
            "name": "Серия 2",
            "uuid": "uuid-ep-2",
            "created_timestamp": 1700000002,
            "hls": {"sd": "/sd/2.m3u8", "hd": None, "fhd": None},
            "preview": None,
            "skips": {"opening": [], "ending": []},
        },
    ],
}

# AniMedia: player.list is a dict {"1": {...}, "2": {...}}
ANIMEDIA_PLAYER = {
    "host": "online.animedia.ac",
    "list": {
        "1": {
            "episode": 1,
            "name": "Серия 1",
            "uuid": "am-uuid-1",
            "created_timestamp": 1700000001,
            "hls": {"sd": "https://cdn.am.ac/ep1/sd.m3u8", "hd": "", "fhd": ""},
            "preview": None,
            "skips": {"opening": [None, None], "ending": [None, None]},
        },
        "2": {
            "episode": 2,
            "name": "Серия 2",
            "uuid": "am-uuid-2",
            "created_timestamp": 0,
            "hls": {"sd": "https://cdn.am.ac/ep2/sd.m3u8", "hd": "", "fhd": ""},
            "preview": None,
            "skips": {"opening": [None, None], "ending": [None, None]},
        },
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestProcessEpisodesListFormat:
    """AniLiberty-style list player.list."""

    def test_saves_two_episodes(self):
        pm, sm = make_process_manager()
        payload = {"title_id": 42, "player": ANILIBERTY_PLAYER}
        pm.process_episodes(payload)
        assert len(sm.saved) == 2

    def test_title_id_injected_from_payload(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 99, "player": ANILIBERTY_PLAYER})
        for ep in sm.saved:
            assert ep["title_id"] == 99

    def test_episode_numbers_correct(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 1, "player": ANILIBERTY_PLAYER})
        nums = sorted(ep["episode_number"] for ep in sm.saved)
        assert nums == [1, 2]

    def test_hls_fields_mapped(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 1, "player": ANILIBERTY_PLAYER})
        ep1 = next(ep for ep in sm.saved if ep["episode_number"] == 1)
        assert ep1["hls_sd"] == "/sd/1.m3u8"
        assert ep1["hls_hd"] == "/hd/1.m3u8"
        assert ep1["hls_fhd"] == "/fhd/1.m3u8"

    def test_uuid_forwarded(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 1, "player": ANILIBERTY_PLAYER})
        ep1 = next(ep for ep in sm.saved if ep["episode_number"] == 1)
        assert ep1["uuid"] == "uuid-ep-1"

    def test_preview_path_forwarded(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 1, "player": ANILIBERTY_PLAYER})
        ep1 = next(ep for ep in sm.saved if ep["episode_number"] == 1)
        assert ep1["preview_path"] == "/preview/1.jpg"

    def test_preview_path_none_allowed(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 1, "player": ANILIBERTY_PLAYER})
        ep2 = next(ep for ep in sm.saved if ep["episode_number"] == 2)
        assert ep2["preview_path"] is None

    def test_skips_serialised_to_json(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 1, "player": ANILIBERTY_PLAYER})
        ep1 = next(ep for ep in sm.saved if ep["episode_number"] == 1)
        # opening skips: [5, 90]
        assert json.loads(ep1["skips_opening"]) == [5, 90]
        assert json.loads(ep1["skips_ending"]) == [1350, 1440]

    def test_created_timestamp_converted_from_unix(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 1, "player": ANILIBERTY_PLAYER})
        ep1 = next(ep for ep in sm.saved if ep["episode_number"] == 1)
        expected = datetime.fromtimestamp(1700000001, tz=timezone.utc)
        assert ep1["created_timestamp"] == expected

    def test_zero_timestamp_uses_epoch(self):
        """created_timestamp=0 should map to epoch, not be treated as missing."""
        pm, sm = make_process_manager()
        player = {
            "host": "",
            "list": [{
                "episode": 5,
                "name": "Ep5",
                "uuid": "x",
                "created_timestamp": 0,
                "hls": {"sd": "/sd.m3u8", "hd": None, "fhd": None},
                "preview": None,
                "skips": {"opening": [], "ending": []},
            }],
        }
        pm.process_episodes({"title_id": 1, "player": player})
        ep = sm.saved[0]
        assert ep["created_timestamp"] == datetime.fromtimestamp(0, tz=timezone.utc)


class TestProcessEpisodesDictFormat:
    """AniMedia-style dict player.list."""

    def test_saves_both_episodes(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 55, "player": ANIMEDIA_PLAYER})
        assert len(sm.saved) == 2

    def test_title_id_from_payload(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 55, "player": ANIMEDIA_PLAYER})
        for ep in sm.saved:
            assert ep["title_id"] == 55

    def test_episode_numbers_match_dict_keys(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 55, "player": ANIMEDIA_PLAYER})
        nums = sorted(ep["episode_number"] for ep in sm.saved)
        assert nums == [1, 2]

    def test_hls_sd_mapped(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 55, "player": ANIMEDIA_PLAYER})
        ep1 = next(ep for ep in sm.saved if ep["episode_number"] == 1)
        assert ep1["hls_sd"] == "https://cdn.am.ac/ep1/sd.m3u8"


class TestProcessEpisodesEdgeCases:
    """Edge cases and failure modes."""

    def test_no_episodes_no_saves(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 1, "player": {"host": "", "list": []}})
        assert sm.saved == []

    def test_empty_dict_list_no_saves(self):
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 1, "player": {"host": "", "list": {}}})
        assert sm.saved == []

    def test_episode_without_hls_key_is_skipped(self):
        """Episodes without 'hls' key (e.g. announced but unreleased) are skipped."""
        pm, sm = make_process_manager()
        player = {
            "host": "",
            "list": [
                # This one has no hls key — pending episode
                {"episode": 3, "name": "Coming soon", "uuid": "x"},
                # This one has hls — should be saved
                {
                    "episode": 4,
                    "name": "Ep4",
                    "uuid": "y",
                    "created_timestamp": 0,
                    "hls": {"sd": "/sd/4.m3u8", "hd": None, "fhd": None},
                    "preview": None,
                    "skips": {"opening": [], "ending": []},
                },
            ],
        }
        pm.process_episodes({"title_id": 1, "player": player})
        assert len(sm.saved) == 1
        assert sm.saved[0]["episode_number"] == 4

    def test_none_player_list_no_crash(self):
        pm, sm = make_process_manager()
        # list is None — should not crash
        result = pm.process_episodes({"title_id": 1, "player": {"host": "", "list": None}})
        assert sm.saved == []
        # Returns False (logged error path) or None — not True; but crucially does not raise
        assert result is not True

    def test_missing_player_key_no_crash(self):
        pm, sm = make_process_manager()
        result = pm.process_episodes({"title_id": 1})
        assert sm.saved == []

    def test_title_id_none_still_forwards(self):
        """title_id=None is forwarded — save_episode handles the FK constraint."""
        pm, sm = make_process_manager()
        player = {
            "host": "",
            "list": [{
                "episode": 1,
                "name": "Ep1",
                "uuid": "z",
                "created_timestamp": 0,
                "hls": {"sd": "/sd.m3u8", "hd": None, "fhd": None},
                "preview": None,
                "skips": {"opening": [], "ending": []},
            }],
        }
        pm.process_episodes({"title_id": None, "player": player})
        assert sm.saved[0]["title_id"] is None  # SaveManager sees NULL → FK error handled there


class TestEpisodeNaturalKey:
    """
    Verify the natural key strategy documented in save_episode:
    Lookup order is (title_id, episode_number) first, uuid second.

    Since we can't run real SQLAlchemy here, we verify that the
    process_episodes call produces the right (title_id, episode_number) pairs
    so save_episode can perform the lookup.
    """

    def test_stable_key_is_title_id_plus_episode_number(self):
        """
        For any provider payload, the episode dict must carry both
        title_id and episode_number — these are the natural key used
        by save_episode to decide insert vs. update.
        """
        pm, sm = make_process_manager()
        pm.process_episodes({"title_id": 77, "player": ANILIBERTY_PLAYER})

        for ep_data in sm.saved:
            assert "title_id" in ep_data and ep_data["title_id"] == 77
            assert "episode_number" in ep_data and isinstance(ep_data["episode_number"], int)

    def test_repeat_process_calls_save_episode_same_count(self):
        """
        process_episodes is idempotent at the call level: it always
        calls save_episode the same number of times with the same natural keys.
        The upsert logic inside save_episode handles the dedup.
        """
        pm, sm = make_process_manager()
        payload = {"title_id": 1, "player": ANILIBERTY_PLAYER}
        pm.process_episodes(payload)
        count_1 = len(sm.saved)

        pm.process_episodes(payload)
        count_2 = len(sm.saved) - count_1

        assert count_1 == count_2 == 2, (
            "each call should produce exactly 2 save_episode calls "
            f"(first={count_1}, second={count_2})"
        )
