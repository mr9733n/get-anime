import asyncio
import pytest

from app.core.use_cases.title_search_use_case import TitleSearchUseCase


class FakeDB:
    def __init__(self, *, keywords_result=None, search_rows=None, raise_on=None):
        self.keywords_result = keywords_result or (None, [])
        self.search_rows = search_rows or []
        self.raise_on = raise_on
        self.calls = {"get_titles_by_keywords": 0, "get_titles_search_query": 0}

    def get_titles_by_keywords(self, search_text: str):
        self.calls["get_titles_by_keywords"] += 1
        if self.raise_on == "get_titles_by_keywords":
            raise RuntimeError("boom-db-keywords")
        return self.keywords_result

    def get_titles_search_query(self, search_text: str):
        self.calls["get_titles_search_query"] += 1
        if self.raise_on == "get_titles_search_query":
            raise RuntimeError("boom-db-search-query")
        return self.search_rows


class FakeAPI:
    def __init__(self):
        self.calls = {"get_release_full": 0, "get_releases_full": 0, "get_search_by_title": 0}
        self.payloads = {}

    def get_release_full(self, rid: int):
        self.calls["get_release_full"] += 1
        return self.payloads.get(("get_release_full", rid), {"external_id": rid})

    def get_releases_full(self, rids: list[int]):
        self.calls["get_releases_full"] += 1
        return self.payloads.get(("get_releases_full", tuple(rids)), {"list": [{"external_id": x} for x in rids]})

    def get_search_by_title(self, text: str):
        self.calls["get_search_by_title"] += 1
        return self.payloads.get(("get_search_by_title", text), {"list": [{"external_id": 1}]})


class FakePersistence:
    def __init__(self):
        self.calls = {"invoke_database_save": 0}
        self.last_saved = None

    def invoke_database_save(self, title_list):
        self.calls["invoke_database_save"] += 1
        self.last_saved = title_list
        # имитируем сохранение: вернем title_id-шники
        return [t.get("title_id", 1000 + i) for i, t in enumerate(title_list)]


class FakeAniMedia:
    def __init__(self, *, data=None, raise_exc: Exception | None = None):
        self.data = data if data is not None else {"list": [{"external_id": 77}]}
        self.raise_exc = raise_exc
        self.calls = 0

    async def get_by_title(self, search_text: str, max_titles: int):
        self.calls += 1
        if self.raise_exc:
            raise self.raise_exc
        return self.data


def make_uc(*, db=None, api=None, persistence=None, animedia=None):
    return TitleSearchUseCase(
        db=db or FakeDB(),
        api=api or FakeAPI(),
        persistence=persistence or FakePersistence(),
        animedia_adapter=animedia or FakeAniMedia(),
        provider_aniliberty="aniliberty",
        provider_animedia="animedia",
    )


def run(coro):
    return asyncio.run(coro)


def test_search_empty_text_returns_error_and_does_not_touch_providers():
    api = FakeAPI()
    animedia = FakeAniMedia()
    uc = make_uc(api=api, animedia=animedia)

    out = run(uc.search_by_title("   ", None))
    assert out.ok is False
    assert "Empty" in (out.error or "")

    assert api.calls["get_search_by_title"] == 0
    assert animedia.calls == 0


def test_search_db_hit_short_circuits_external():
    db = FakeDB(keywords_result=([1, 2], ["aniliberty", "aniliberty"]))
    api = FakeAPI()
    animedia = FakeAniMedia()
    uc = make_uc(db=db, api=api, animedia=animedia)

    out = run(uc.search_by_title("naruto", None))
    assert out.ok is True
    assert out.title_ids == [1, 2]
    assert out.used_provider is None  # db-hit

    assert api.calls["get_search_by_title"] == 0
    assert animedia.calls == 0


def test_search_db_hit_but_provider_filter_mismatch_falls_back_to_external():
    # DB нашла, но providers не совпадают с фильтром -> идём наружу
    db = FakeDB(keywords_result=([1], ["aniliberty"]))
    api = FakeAPI()
    persistence = FakePersistence()
    uc = make_uc(db=db, api=api, persistence=persistence)

    out = run(uc.search_by_title("naruto", "animedia"))
    assert out.ok is True
    assert out.used_provider == "animedia"
    assert persistence.calls["invoke_database_save"] == 1


def test_search_external_aniliberty_success():
    db = FakeDB(keywords_result=(None, []))
    api = FakeAPI()
    api.payloads[("get_search_by_title", "naruto")] = {"list": [{"title_id": 10}]}
    persistence = FakePersistence()
    animedia = FakeAniMedia()
    uc = make_uc(db=db, api=api, persistence=persistence, animedia=animedia)

    out = run(uc.search_by_title("naruto", None))
    assert out.ok is True
    assert out.used_provider == "aniliberty"
    assert persistence.calls["invoke_database_save"] == 1
    assert animedia.calls == 0  # не дошли до fallback


def test_search_external_fallback_to_animedia_when_aniliberty_errors():
    db = FakeDB(keywords_result=(None, []))
    api = FakeAPI()
    api.payloads[("get_search_by_title", "naruto")] = {"error": "provider down"}
    persistence = FakePersistence()
    animedia = FakeAniMedia(data={"list": [{"title_id": 55}]})
    uc = make_uc(db=db, api=api, persistence=persistence, animedia=animedia)

    out = run(uc.search_by_title("naruto", None))
    assert out.ok is True
    assert out.used_provider == "animedia"
    assert animedia.calls == 1


def test_update_titles_empty_text_returns_error():
    uc = make_uc()
    out = run(uc.update_titles("   ", None))
    assert out.ok is False
    assert "Empty" in (out.error or "")


def test_update_titles_aniliberty_happy_path_updates_one_row():
    db = FakeDB(search_rows=[
        {"title_id": 1, "providers": [{"provider": "aniliberty", "external_id": 123}], "name_en": "X", "name_ru": "Y"},
    ])
    api = FakeAPI()
    api.payloads[("get_release_full", 123)] = {"external_id": 123, "title_id": 999}
    persistence = FakePersistence()
    uc = make_uc(db=db, api=api, persistence=persistence)

    out = run(uc.update_titles("X", None))
    assert out.ok is True
    assert out.updated >= 1
    assert out.failed == 0
    assert api.calls["get_release_full"] == 1
    assert persistence.calls["invoke_database_save"] == 1
