from __future__ import annotations

import threading
from collections.abc import Callable, Iterable


Work = Callable[[], dict]


class ProviderWriteQueue:
    """Serialize accepted provider writes and retain failures for explicit retry."""

    def __init__(
        self,
        *,
        provider: str,
        provider_name: str,
        background_runner: Callable[[Callable[[], None]], None],
        failure_keys: Iterable[str],
    ) -> None:
        self._provider = provider
        self._provider_name = provider_name
        self._background_runner = background_runner
        self._failure_keys = tuple(failure_keys)
        self._pending: list[Work] = []
        self._failed: list[Work] = []
        self._worker_running = False
        self._activity: dict | None = None
        self._lock = threading.Lock()

    def submit(self, work: Work) -> None:
        with self._lock:
            self._pending.append(work)
            pending_count = len(self._pending)
            self._activity = self._working_activity(
                label=f"{self._provider_name} writes running",
                message=(
                    f"Threadwise is applying {pending_count} accepted "
                    f"{self._provider_name} change{'s' if pending_count != 1 else ''} in order."
                ),
            )
            if self._worker_running:
                return
            self._worker_running = True
        self._background_runner(self._run)

    def retry(self) -> dict:
        with self._lock:
            if self._worker_running:
                raise ValueError(f"{self._provider_name} writes are still running.")
            if not self._failed:
                raise ValueError(f"There are no failed {self._provider_name} writes to retry.")
            self._pending.extend(self._failed)
            self._failed.clear()
            self._worker_running = True
            self._activity = self._working_activity(
                label=f"Retrying {self._provider_name} writes",
                message=f"Threadwise is retrying the failed {self._provider_name} changes in order.",
            )
        self._background_runner(self._run)
        return self.activity() or {}

    def activity(self) -> dict | None:
        with self._lock:
            return dict(self._activity) if self._activity else None

    def _working_activity(self, *, label: str, message: str) -> dict:
        return {
            "id": f"{self._provider}-teaching-write",
            "kind": "provider-write",
            "state": "working",
            "label": label,
            "message": message,
            "provider": self._provider,
        }

    def _run(self) -> None:
        completed = 0
        while True:
            with self._lock:
                if not self._pending:
                    self._worker_running = False
                    self._activity = self._finished_activity(completed)
                    return
                work = self._pending.pop(0)
            try:
                summary = work() or {}
                failed = any(int(summary.get(key) or 0) for key in self._failure_keys)
            except Exception:
                failed = True
            with self._lock:
                if failed:
                    self._failed.append(work)
                else:
                    completed += 1

    def _finished_activity(self, completed: int) -> dict:
        failed_count = len(self._failed)
        failed_suffix = "s" if failed_count != 1 else ""
        completed_suffix = "s" if completed != 1 else ""
        return {
            "id": f"{self._provider}-teaching-write",
            "kind": "provider-write",
            "state": "error" if failed_count else "done",
            "label": (
                f"{self._provider_name} writes need attention"
                if failed_count
                else f"{self._provider_name} labels applied"
            ),
            "message": (
                f"{failed_count} accepted {self._provider_name} change{failed_suffix} could not be confirmed."
                if failed_count
                else f"{completed} accepted {self._provider_name} change{completed_suffix} confirmed."
            ),
            "provider": self._provider,
            **(
                {"action": "retry-provider-write", "action_label": "Try again"}
                if failed_count
                else {}
            ),
        }
