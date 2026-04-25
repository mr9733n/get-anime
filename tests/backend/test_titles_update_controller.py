"""
Regression tests for TitlesUpdateController.

Primary regression being guarded:
  AniMedia wrong-query bug — a title without an AniMedia provider link
  must NOT reach the adapter with query=<local_title_id> (a bare integer
  that was accidentally passed as a search query: story=2002).

  Correct behaviour:
    * No AniMedia link → external_id = None → query = title name (name_en /
      name_ru / code), never the numeric local title_id.
    * AniMedia link present (legacy bare-id "2002") → compound "2002@@Name"
      built automatically; external_id is passed, query = None.
    * AniMedia link present with compound token → forwarded as-is.

Tests use in-process fakes; no real DB or network required.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend.core.controllers.titles_update_controller import TitlesUpdateController


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

def title(
    *,
    title_id: int,
    name_en: str = "",
    name_ru: str = "",
    code: str = "",
    alternative_name: str = "",
    provider_links: list[dict] | None = None,
    provider_code: str | None = None,
) -> SimpleNamespace:
    """Simulate a title DTO as returned by TitlesController.titles_get()."""
    return SimpleNamespace(
        title_id=title_id,
        name_en=name_en,
        name_ru=name_ru,
        code=code,
        alternative_name=alternative_name,
        provider_links=provider_links or [],
        provider_code=provider_code,
    )


def aniliberty_link(external_id: str | int) -> dict:
    return {"provider_code": "aniliberty", "external_title_id": str(external_id)}


def animedia_link(external_id: str | int) -> dict:
    return {"provider_code": "animedia", "external_title_id": str(external_id)}


class FakeTitlesController:
    """Returns a fixed list of DTOs for any titles_get() call."""

    def __init__(self, dtos: list):
        self._dtos = dtos

    def titles_get(self, *, title_ids, user_id=42, enrich=True, **_):
        return self._dtos


class FakeSyncController:
    """Records all fetch_and_process() calls and returns a stub result."""

    def __init__(self):
        self.calls: list[dict] = []

    async def fetch_and_process(
        self,
        *,
        provider_code: str,
        external_id=None,
        query=None,
        mode: str = "title_full",
        max_results: int = 5,
    ):
        self.calls.append(
            {
                "provider_code": provider_code,
                "external_id": external_id,
                "query": query,
                "mode": mode,
                "max_results": max_results,
            }
        )
        return {"ok": True, "provider_code": provider_code}


def make_controller(dtos: list) -> tuple[TitlesUpdateController, FakeSyncController]:
    sync = FakeSyncController()
    ctrl = TitlesUpdateController(
        titles=FakeTitlesController(dtos),
        sync=sync,
    )
    return ctrl, sync


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Unit tests: static helpers
# ---------------------------------------------------------------------------

class TestPickExternalIdFromLinks:
    """_pick_external_id_from_links() correctness."""

    def test_no_links_returns_none(self):
        t = title(title_id=1, name_en="Show")
        assert TitlesUpdateController._pick_external_id_from_links(t, "animedia") is None

    def test_different_provider_link_returns_none(self):
        t = title(title_id=1, name_en="Show", provider_links=[aniliberty_link("123")])
        assert TitlesUpdateController._pick_external_id_from_links(t, "animedia") is None

    def test_aniliberty_link_returned_verbatim(self):
        t = title(title_id=1, provider_links=[aniliberty_link("123")])
        result = TitlesUpdateController._pick_external_id_from_links(t, "aniliberty")
        assert result == "123"

    def test_animedia_compound_token_returned_verbatim(self):
        t = title(title_id=1, provider_links=[animedia_link("2002@@One Punch Man")])
        result = TitlesUpdateController._pick_external_id_from_links(t, "animedia")
        assert result == "2002@@One Punch Man"

    def test_animedia_bare_id_rebuilds_compound_token(self):
        """Legacy row with bare numeric id → auto-rebuild "id@@name"."""
        t = title(title_id=42, name_en="One Punch Man", provider_links=[animedia_link("2002")])
        result = TitlesUpdateController._pick_external_id_from_links(t, "animedia")
        assert result == "2002@@One Punch Man"

    def test_animedia_bare_id_without_name_returns_bare_id(self):
        """No name available → bare id is still returned (not None), adapter deals with it."""
        t = title(title_id=42, provider_links=[animedia_link("2002")])
        result = TitlesUpdateController._pick_external_id_from_links(t, "animedia")
        # no name so can't build compound — returns bare id
        assert result == "2002"

    def test_none_external_title_id_returns_none(self):
        link = {"provider_code": "aniliberty", "external_title_id": None}
        t = title(title_id=1, provider_links=[link])
        assert TitlesUpdateController._pick_external_id_from_links(t, "aniliberty") is None


class TestFallbackQuery:
    """_fallback_query() must never return a numeric local title_id."""

    def test_prefers_name_en(self):
        t = title(title_id=99, name_en="One Punch Man", name_ru="Ван Панч Мэн", code="one-punch-man")
        assert TitlesUpdateController._fallback_query(t) == "One Punch Man"

    def test_falls_back_to_name_ru_when_no_en(self):
        t = title(title_id=99, name_en="", name_ru="Ван Панч Мэн", code="one-punch-man")
        assert TitlesUpdateController._fallback_query(t) == "Ван Панч Мэн"

    def test_falls_back_to_code_when_no_names(self):
        t = title(title_id=99, name_en="", name_ru="", code="one-punch-man")
        assert TitlesUpdateController._fallback_query(t) == "one-punch-man"

    def test_returns_none_when_all_empty(self):
        t = title(title_id=99, name_en="", name_ru="", code="")
        assert TitlesUpdateController._fallback_query(t) is None

    def test_numeric_title_id_is_never_returned(self):
        """The bug: title_id (e.g. 2002) was used as query → story=2002 in URL."""
        t = title(title_id=2002, name_en="", name_ru="", code="")
        result = TitlesUpdateController._fallback_query(t)
        assert result != 2002
        assert result != "2002"
        assert result is None

    def test_whitespace_only_name_treated_as_missing(self):
        t = title(title_id=5, name_en="   ", name_ru="", code="")
        assert TitlesUpdateController._fallback_query(t) is None

    def test_falls_back_to_alternative_name_when_others_missing(self):
        """alternative_name is used after name_en/name_ru/code are all empty."""
        t = title(title_id=7, name_en="", name_ru="", code="", alternative_name="Wan Panchu Man")
        assert TitlesUpdateController._fallback_query(t) == "Wan Panchu Man"

    def test_primary_name_takes_precedence_over_alternative(self):
        t = title(title_id=7, name_en="One Punch Man", alternative_name="Wan Panchu Man")
        assert TitlesUpdateController._fallback_query(t) == "One Punch Man"

    def test_alternative_name_used_as_query_in_update(self):
        """End-to-end: when only alternative_name is available, it's used as query."""
        t = title(
            title_id=3,
            name_en="",
            name_ru="",
            code="",
            alternative_name="One Punch Man",
            provider_links=[],
        )
        ctrl, sync = make_controller([t])
        run(ctrl.update_titles(title_ids=[3], provider_code="animedia"))

        assert len(sync.calls) == 1
        assert sync.calls[0]["query"] == "One Punch Man"
        assert sync.calls[0]["external_id"] is None


# ---------------------------------------------------------------------------
# Regression: update_titles calls fetch_and_process with correct args
# ---------------------------------------------------------------------------

class TestUpdateTitlesQueryRouting:
    """
    Core regression: the sync call must use a name-based query, not the
    local numeric title_id, when no provider link exists.
    """

    def test_no_animedia_link_uses_name_as_query(self):
        """
        REGRESSION: title_id=2002 without AniMedia link must NOT produce
        query="2002" or external_id=2002.  The correct query is the title name.
        """
        t = title(
            title_id=2002,
            name_en="One Punch Man",
            provider_links=[],  # no AniMedia link at all
        )
        ctrl, sync = make_controller([t])
        run(ctrl.update_titles(title_ids=[2002], provider_code="animedia"))

        assert len(sync.calls) == 1
        call = sync.calls[0]
        assert call["provider_code"] == "animedia"
        # external_id must be None — no link
        assert call["external_id"] is None
        # query must be the title name, never the numeric id
        assert call["query"] == "One Punch Man"
        assert call["query"] != 2002
        assert call["query"] != "2002"

    def test_animedia_link_present_uses_external_id_not_query(self):
        t = title(
            title_id=10,
            name_en="One Punch Man",
            provider_links=[animedia_link("2002@@One Punch Man")],
        )
        ctrl, sync = make_controller([t])
        run(ctrl.update_titles(title_ids=[10], provider_code="animedia"))

        assert len(sync.calls) == 1
        call = sync.calls[0]
        assert call["external_id"] == "2002@@One Punch Man"
        assert call["query"] is None

    def test_legacy_bare_animedia_id_uses_compound_external_id(self):
        """Legacy link with bare "2002" → compound token forwarded as external_id."""
        t = title(
            title_id=10,
            name_en="One Punch Man",
            provider_links=[animedia_link("2002")],
        )
        ctrl, sync = make_controller([t])
        run(ctrl.update_titles(title_ids=[10], provider_code="animedia"))

        assert len(sync.calls) == 1
        call = sync.calls[0]
        assert call["external_id"] == "2002@@One Punch Man"
        assert call["query"] is None

    def test_aniliberty_with_link_uses_external_id(self):
        t = title(
            title_id=5,
            name_en="My Hero Academia",
            provider_links=[aniliberty_link("9000")],
        )
        ctrl, sync = make_controller([t])
        run(ctrl.update_titles(title_ids=[5], provider_code="aniliberty"))

        assert len(sync.calls) == 1
        call = sync.calls[0]
        assert call["external_id"] == "9000"
        assert call["query"] is None
        assert call["provider_code"] == "aniliberty"

    def test_aniliberty_without_link_uses_name_query(self):
        t = title(title_id=5, name_en="My Hero Academia", provider_links=[])
        ctrl, sync = make_controller([t])
        run(ctrl.update_titles(title_ids=[5], provider_code="aniliberty"))

        assert len(sync.calls) == 1
        call = sync.calls[0]
        assert call["external_id"] is None
        assert call["query"] == "My Hero Academia"

    def test_title_with_no_name_and_no_link_is_skipped(self):
        """No name + no link → nothing we can query with → skipped."""
        t = title(title_id=7, name_en="", name_ru="", code="", provider_links=[])
        ctrl, sync = make_controller([t])
        result = run(ctrl.update_titles(title_ids=[7], provider_code="animedia"))

        assert sync.calls == []
        assert result["skipped"] == 1

    def test_multiple_titles_all_correctly_routed(self):
        t_with_link = title(
            title_id=1,
            name_en="Show A",
            provider_links=[animedia_link("100@@Show A")],
        )
        t_without_link = title(
            title_id=2,
            name_en="Show B",
            provider_links=[],
        )
        ctrl, sync = make_controller([t_with_link, t_without_link])
        run(ctrl.update_titles(title_ids=[1, 2], provider_code="animedia"))

        assert len(sync.calls) == 2

        call_a = next(c for c in sync.calls if c["external_id"] == "100@@Show A")
        assert call_a["query"] is None

        call_b = next(c for c in sync.calls if c["external_id"] is None)
        assert call_b["query"] == "Show B"

    def test_mode_and_max_results_forwarded(self):
        t = title(title_id=1, name_en="Show", provider_links=[])
        ctrl, sync = make_controller([t])
        run(ctrl.update_titles(
            title_ids=[1],
            provider_code="aniliberty",
            mode="title",
            max_results=3,
        ))

        assert sync.calls[0]["mode"] == "title"
        assert sync.calls[0]["max_results"] == 3


class TestUpdateTitlesProviderResolution:
    """_pick_provider_from_title() and provider_code param routing."""

    def test_explicit_provider_code_overrides_link(self):
        t = title(
            title_id=1,
            name_en="Show",
            provider_links=[aniliberty_link("10")],
        )
        ctrl, sync = make_controller([t])
        # Force animedia even though the link is aniliberty
        run(ctrl.update_titles(title_ids=[1], provider_code="animedia"))

        # No animedia link → fallback to name query
        assert sync.calls[0]["provider_code"] == "animedia"
        assert sync.calls[0]["query"] == "Show"

    def test_no_provider_code_resolves_from_link(self):
        t = title(
            title_id=1,
            name_en="Naruto",
            provider_links=[aniliberty_link("42")],
        )
        ctrl, sync = make_controller([t])
        run(ctrl.update_titles(title_ids=[1], provider_code=None))

        assert sync.calls[0]["provider_code"] == "aniliberty"
        assert sync.calls[0]["external_id"] == "42"

    def test_no_provider_code_no_links_skipped(self):
        t = title(title_id=1, name_en="Show", provider_links=[])
        ctrl, sync = make_controller([t])
        result = run(ctrl.update_titles(title_ids=[1], provider_code=None))

        assert sync.calls == []
        assert result["skipped"] == 1

    def test_return_structure(self):
        t = title(title_id=1, name_en="Show", provider_links=[aniliberty_link("9")])
        ctrl, sync = make_controller([t])
        result = run(ctrl.update_titles(title_ids=[1], provider_code="aniliberty"))

        assert result["ok"] is True
        assert isinstance(result["applied"], list)
        assert result["skipped"] == 0
        assert result["error"] is None
