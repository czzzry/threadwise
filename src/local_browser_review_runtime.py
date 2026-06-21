from pathlib import Path

from src.gmail_fetcher import GmailBatchFetcher
from src.live_gmail_client import LiveGmailClient, SetupError
from src.local_batch_summary import load_batch
from src.shadow_label_eval import OpenAIShadowLabelClient, ShadowLabelEvaluator


def build_live_fetch_batch_fn(
    storage_dir: Path,
    credentials_dir: Path,
    client_secret_path: Path | None,
    batch_size: int,
):
    def fetch_batch(account_id: str) -> dict | None:
        try:
            gmail_client = LiveGmailClient.from_local_oauth(
                account_id,
                credentials_dir,
                client_secret_path=client_secret_path,
            )
            fetcher = GmailBatchFetcher(gmail_client=gmail_client, storage_dir=storage_dir)
            review_queue = fetcher.fetch_gmail_batch(account_id, batch_size)
        except SetupError as exc:
            raise RuntimeError(str(exc)) from exc

        if review_queue is None:
            return None

        batch = load_batch(storage_dir / "batches" / f"{review_queue['batch_id']}.json")
        review_queue["fetch_failures"] = batch.get("fetch_failures", [])
        return review_queue

    return fetch_batch


def build_shadow_eval_fn(storage_dir: Path):
    def run_shadow_eval(limit: int) -> dict:
        evaluator = ShadowLabelEvaluator(
            storage_dir=storage_dir,
            model_client=OpenAIShadowLabelClient.from_env("gpt-4.1-mini"),
        )
        report = evaluator.run(limit=limit, disagreement_limit=limit)
        report_path = Path(report["report_path"])
        return {
            "evaluation_id": report_path.stem,
            "reviewed_count": report["overall"]["reviewed_count"],
            "comparison_count": len(report.get("comparison_candidates", [])),
            "report_path": report["report_path"],
        }

    return run_shadow_eval
