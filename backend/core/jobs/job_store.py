"""
In-memory thread-safe job registry.

Used by titles.update.start / jobs.get to track long-running background
update jobs without blocking the caller.

Lifecycle:
  queued  → job created, thread about to start
  running → background thread is executing the update
  done    → update completed successfully; result contains the payload
  error   → update raised an exception; error contains the message
"""
from __future__ import annotations

import copy
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class JobStatus:
    job_id: str
    op: str
    status: str              # "queued" | "running" | "done" | "error"
    params: dict

    result: Any | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: str | None = None


class JobStore:
    """Thread-safe in-memory store for background job state."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobStatus] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, op: str, params: dict) -> JobStatus:
        """Create a new job in 'queued' state and return it."""
        job_id = str(uuid.uuid4())
        job = JobStatus(
            job_id=job_id,
            op=op,
            status="queued",
            params=copy.deepcopy(params),
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> JobStatus | None:
        """Return the job with the given id, or None if not found."""
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> None:
        """Update named fields of an existing job. Unknown fields are ignored."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for k, v in kwargs.items():
                if hasattr(job, k):
                    setattr(job, k, v)

    def all_jobs(self) -> list[JobStatus]:
        """Return a snapshot of all jobs (no particular order)."""
        with self._lock:
            return list(self._jobs.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._jobs)
