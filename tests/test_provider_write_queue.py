import unittest

from src.provider_write_queue import ProviderWriteQueue


class ProviderWriteQueueTests(unittest.TestCase):
    def test_runs_rapid_submissions_in_order_with_one_worker(self) -> None:
        workers = []
        calls = []
        queue = ProviderWriteQueue(
            provider="gmail",
            provider_name="Gmail",
            background_runner=workers.append,
            failure_keys=("label_write_failed", "inbox_remove_failed"),
        )

        queue.submit(lambda: calls.append("first") or {})
        queue.submit(lambda: calls.append("second") or {})

        self.assertEqual(len(workers), 1)
        self.assertEqual(queue.activity()["state"], "working")
        workers[0]()
        self.assertEqual(calls, ["first", "second"])
        self.assertEqual(queue.activity()["state"], "done")

    def test_retains_failed_work_and_retries_it(self) -> None:
        workers = []
        calls = []
        queue = ProviderWriteQueue(
            provider="protonmail",
            provider_name="Proton Mail",
            background_runner=workers.append,
            failure_keys=("label_write_failed",),
        )

        def work() -> dict:
            calls.append("called")
            return {"label_write_failed": int(len(calls) == 1)}

        queue.submit(work)
        workers.pop(0)()
        self.assertEqual(queue.activity()["state"], "error")
        self.assertEqual(queue.activity()["action"], "retry-provider-write")

        queue.retry()
        workers.pop(0)()
        self.assertEqual(calls, ["called", "called"])
        self.assertEqual(queue.activity()["state"], "done")

    def test_exception_is_a_retryable_failure(self) -> None:
        workers = []
        queue = ProviderWriteQueue(
            provider="gmail",
            provider_name="Gmail",
            background_runner=workers.append,
            failure_keys=("label_write_failed",),
        )
        queue.submit(lambda: (_ for _ in ()).throw(RuntimeError("offline")))
        workers[0]()

        self.assertEqual(queue.activity()["state"], "error")

    def test_gmail_setup_failure_with_zero_counters_is_retryable(self) -> None:
        workers = []
        calls = []
        queue = ProviderWriteQueue(
            provider="gmail",
            provider_name="Gmail",
            background_runner=workers.append,
            failure_keys=("label_write_failed", "inbox_remove_failed"),
        )

        def work() -> dict:
            calls.append("called")
            if len(calls) == 1:
                return {
                    "mode": "gmail-write-failed",
                    "error": "Gmail client secret is unavailable",
                    "label_write_failed": 0,
                    "inbox_remove_failed": 0,
                }
            return {"mode": "applied"}

        queue.submit(work)
        workers.pop(0)()

        self.assertEqual(queue.activity()["state"], "error")
        self.assertEqual(queue.activity()["action"], "retry-provider-write")
        self.assertEqual(queue.activity()["action_label"], "Try again")
        self.assertNotEqual(queue.activity()["label"], "Gmail labels applied")

        queue.retry()
        workers.pop(0)()

        self.assertEqual(calls, ["called", "called"])
        self.assertEqual(queue.activity()["state"], "done")


if __name__ == "__main__":
    unittest.main()
