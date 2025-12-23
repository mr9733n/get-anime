

from providers.aniliberty.v1.service import ReleaseBundleService

def test_episodes_to_list():
    s = ReleaseBundleService(None, None)

    assert s._episodes_to_list(None) == []
    assert s._episodes_to_list([]) == []
    assert s._episodes_to_list({"list": [1, 2]}) == [1, 2]
    assert s._episodes_to_list({"first": 1}) == []

class FakeAPI:
    def get_release_by_id(self, rid):
        return {"id": rid, "episodes": [], "torrents": []}

    def get_release_torrents(self, rid):
        return [{"id": "t"}]

    def get_release_members(self, rid):
        return []

    def get_franchise_by_release(self, rid):
        return []


def test_fetch_bundle_embedded():
    api = FakeAPI()
    s = ReleaseBundleService(api, logger=None)

    out = s.fetch_bundle(1, allow_network=False)
    assert out["id"] == 1
    assert "episodes" in out

def test_fetch_bundles():
    api = FakeAPI()
    s = ReleaseBundleService(api, logger=None)

    out = s.fetch_bundles([1, 2, 3])
    assert set(out.keys()) == {1, 2, 3}

def test_fetch_bundle_embedded_dict_episodes():
    class API(FakeAPI):
        def get_release_by_id(self, rid):
            return {"id": rid, "episodes": {"list": [{"id": 1}]}}

    s = ReleaseBundleService(API(), logger=None)
    out = s.fetch_bundle(1, allow_network=False)
    assert out["episodes"] == [{"id": 1}]

def test_service_uses_embedded_episodes_and_normalizes():
    class API:
        def get_release_by_id(self, rid):
            return {"id": rid, "episodes": {"list": [{"id": 1}]}}

        # extras пусть будут, но мы их не используем в этом тесте
        def get_release_torrents(self, rid):  # pragma: no cover
            raise AssertionError("Should not be called")

        def get_release_members(self, rid):  # pragma: no cover
            raise AssertionError("Should not be called")

        def get_franchise_by_release(self, rid):  # pragma: no cover
            raise AssertionError("Should not be called")

    s = ReleaseBundleService(API(), logger=None)
    out = s.fetch_bundle(1, allow_network=False, prefer_embedded=True)

    assert out["episodes"] == [{"id": 1}]

def test_service_allow_network_false_does_not_call_extras():
    class API:
        def get_release_by_id(self, rid):
            return {"id": rid, "episodes": []}

        def get_release_torrents(self, rid):
            raise AssertionError("should not call torrents when allow_network=False")

        def get_release_members(self, rid):
            raise AssertionError("should not call members when allow_network=False")

        def get_franchise_by_release(self, rid):
            raise AssertionError("should not call franchise when allow_network=False")

    s = ReleaseBundleService(API(), logger=None)
    out = s.fetch_bundle(1, allow_network=False, prefer_embedded=True)

    assert out["id"] == 1
    assert "episodes" in out

