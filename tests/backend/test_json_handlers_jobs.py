"""
Tests for titles.update.start / jobs.get handlers and JobStore.

The job system runs the real update coroutine in a daemon thread.
Tests use FakeBackend (from conftest) which has:
  - backend.jobs = JobStore()
  - backend.titles_update = FakeTitlesUpdateController()
  - backend.ctx = FakeBackendContext()

Since the thread fires and completes asynchronously, tests that check
final job state poll with a short timeout (max 1 second).
"""
from __future__ import annotations

import time

import pytest

from backend.core.jobs.job_store import JobStore, JobStatus
from tests.conftest import call_op, FakeBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_status(backend, job_id: str, expected: str, timeout: float = 2.0) -> dict:
    """Poll jobs.get until status == expected or timeout, return last response."""
    deadline = time.monotonic() + timeout
    last_res = {}
    while time.monotonic() < deadline:
        last_res = call_op(backend, "jobs.get", {"job_id": job_id})
        if last_res.get("ok") and last_res["result"]["job"]["status"] == expected:
            return last_res
        time.sleep(0.02)
    return last_res


# ---------------------------------------------------------------------------
# JobStore unit tests (no handlers, no network)
# ---------------------------------------------------------------------------

class TestJobStore:
    def test_create_returns_queued_job(self):
        store = JobStore()
        job = store.create("titles.update", {"title_ids": [1]})
        assert job.status == "queued"
        assert job.op == "titles.update"
        assert isinstance(job.job_id, str) and len(job.job_id) == 36  # UUID4

    def test_get_returns_same_object(self):
        store = JobStore()
        job = store.create("op", {})
        assert store.get(job.job_id) is job

    def test_get_missing_returns_none(self):
        store = JobStore()
        assert store.get("nonexistent-id") is None

    def test_update_changes_fields(self):
        store = JobStore()
        job = store.create("op", {})
        store.update(job.job_id, status="running", progress="50%")
        assert job.status == "running"
        assert job.progress == "50%"

    def test_update_unknown_field_ignored(self):
        store = JobStore()
        job = store.create("op", {})
        store.update(job.job_id, totally_unknown_field="boom")  # must not raise
        assert job.status == "queued"

    def test_update_missing_id_does_not_raise(self):
        store = JobStore()
        store.update("no-such-id", status="done")  # must not raise

    def test_all_jobs_returns_snapshot(self):
        store = JobStore()
        a = store.create("op1", {})
        b = store.create("op2", {})
        all_j = store.all_jobs()
        assert len(all_j) == 2
        ids = {j.job_id for j in all_j}
        assert a.job_id in ids and b.job_id in ids

    def test_len(self):
        store = JobStore()
        assert len(store) == 0
        store.create("op", {})
        assert len(store) == 1

    def test_params_not_mutated(self):
        """JobStore copies params — mutations after creation don't bleed through."""
        store = JobStore()
        p = {"title_ids": [1, 2]}
        job = store.create("op", p)
        p["title_ids"].append(99)
        assert job.params["title_ids"] == [1, 2]


# ---------------------------------------------------------------------------
# titles.update.start handler tests
# ---------------------------------------------------------------------------

class TestTitlesUpdateStart:
    def test_returns_ok_with_job_id(self, backend):
        res = call_op(backend, "titles.update.start", {"title_ids": [1]})
        assert res["ok"] is True
        assert "job_id" in res["result"]
        assert len(res["result"]["job_id"]) == 36

    def test_initial_status_is_queued(self, backend):
        res = call_op(backend, "titles.update.start", {"title_ids": [1]})
        assert res["result"]["status"] == "queued"

    def test_job_appears_in_store(self, backend):
        res = call_op(backend, "titles.update.start", {"title_ids": [1]})
        job_id = res["result"]["job_id"]
        job = backend.jobs.get(job_id)
        assert job is not None
        assert job.op == "titles.update"

    def test_returns_immediately_without_waiting(self, backend):
        """Handler must return before the update coroutine finishes."""
        import time
        start = time.monotonic()
        call_op(backend, "titles.update.start", {"title_ids": [1]})
        elapsed = time.monotonic() - start
        # Should complete well under 500 ms even with thread startup
        assert elapsed < 0.5

    def test_missing_title_ids_raises(self, backend):
        with pytest.raises((ValueError, KeyError)):
            call_op(backend, "titles.update.start", {})

    def test_empty_title_ids_raises(self, backend):
        with pytest.raises(ValueError):
            call_op(backend, "titles.update.start", {"title_ids": []})

    def test_provider_code_stored_in_job(self, backend):
        res = call_op(backend, "titles.update.start", {
            "title_ids": [5],
            "provider_code": "aniliberty",
        })
        job_id = res["result"]["job_id"]
        job = backend.jobs.get(job_id)
        assert job.params["provider_code"] == "aniliberty"

    def test_multiple_starts_create_separate_jobs(self, backend):
        r1 = call_op(backend, "titles.update.start", {"title_ids": [1]})
        r2 = call_op(backend, "titles.update.start", {"title_ids": [2]})
        assert r1["result"]["job_id"] != r2["result"]["job_id"]
        assert len(backend.jobs) >= 2


# ---------------------------------------------------------------------------
# jobs.get handler tests
# ---------------------------------------------------------------------------

class TestJobsGet:
    def test_unknown_job_id_returns_not_found(self, backend):
        res = call_op(backend, "jobs.get", {"job_id": "00000000-0000-0000-0000-000000000000"})
        assert res["ok"] is False
        assert res["error"] == "job_not_found"

    def test_missing_job_id_raises(self, backend):
        with pytest.raises(ValueError):
            call_op(backend, "jobs.get", {})

    def test_returns_queued_immediately_after_start(self, backend):
        res = call_op(backend, "titles.update.start", {"title_ids": [1]})
        job_id = res["result"]["job_id"]
        # Poll once right away — may still be queued or already running/done
        status_res = call_op(backend, "jobs.get", {"job_id": job_id})
        assert status_res["ok"] is True
        assert status_res["result"]["job"]["status"] in ("queued", "running", "done")

    def test_job_reaches_done_after_completion(self, backend):
        res = call_op(backend, "titles.update.start", {"title_ids": [1]})
        job_id = res["result"]["job_id"]
        final = wait_for_status(backend, job_id, "done")
        assert final["ok"] is True
        job_data = final["result"]["job"]
        assert job_data["status"] == "done"
        assert job_data["error"] is None
        assert job_data["finished_at"] is not None

    def test_done_job_has_result(self, backend):
        res = call_op(backend, "titles.update.start", {"title_ids": [42]})
        job_id = res["result"]["job_id"]
        final = wait_for_status(backend, job_id, "done")
        job_data = final["result"]["job"]
        assert job_data["result"] is not None
        assert job_data["result"].get("ok") is True

    def test_done_job_has_started_and_finished_timestamps(self, backend):
        res = call_op(backend, "titles.update.start", {"title_ids": [1]})
        job_id = res["result"]["job_id"]
        final = wait_for_status(backend, job_id, "done")
        job_data = final["result"]["job"]
        assert job_data["started_at"] is not None
        assert job_data["finished_at"] is not None

    def test_job_response_contains_required_fields(self, backend):
        res = call_op(backend, "titles.update.start", {"title_ids": [1]})
        job_id = res["result"]["job_id"]
        wait_for_status(backend, job_id, "done")
        status_res = call_op(backend, "jobs.get", {"job_id": job_id})
        job_data = status_res["result"]["job"]
        for field in ("job_id", "op", "status", "error", "started_at", "finished_at", "progress", "result"):
            assert field in job_data, f"missing field: {field}"


# ---------------------------------------------------------------------------
# Error job path
# ---------------------------------------------------------------------------

class TestJobError:
    def test_failing_update_produces_error_status(self, backend):
        """If titles_update.update_titles raises, job status → error."""

        class BrokenUpdateController:
            async def update_titles(self, **_):
                raise RuntimeError("provider offline")

        backend.titles_update = BrokenUpdateController()
        res = call_op(backend, "titles.update.start", {"title_ids": [1]})
        job_id = res["result"]["job_id"]

        final = wait_for_status(backend, job_id, "error")
        job_data = final["result"]["job"]
        assert job_data["status"] == "error"
        assert "provider offline" in (job_data["error"] or "")
        assert job_data["finished_at"] is not None
