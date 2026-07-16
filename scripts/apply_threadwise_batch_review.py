import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from src.gmail_batch_review_store import GmailBatchReviewStore
from src.gmail_cli_support import default_gmail_client_factory
from src.gmail_automation import build_gmail_label_writer
from src.live_gmail_client import GMAIL_MODIFY_SCOPE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply explicit full-body review decisions to one stored Threadwise batch.")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--default-label", required=True)
    parser.add_argument("--override", action="append", default=[], metavar="LABEL=ID,ID")
    parser.add_argument("--storage-dir", type=Path, default=Path("data/gmail_fetch"))
    parser.add_argument("--credentials-dir", type=Path, default=Path("data/gmail_credentials"))
    parser.add_argument("--client-secret-path", type=Path)
    parser.add_argument("--local-only", action="store_true", help="Persist Threadwise decisions without writing Gmail.")
    args = parser.parse_args(argv)

    overrides: dict[str, str] = {}
    for raw in args.override:
        label, separator, ids = raw.partition("=")
        if not separator or not label.strip() or not ids.strip():
            parser.error("--override must use LABEL=ID,ID")
        for message_id in ids.split(","):
            message_id = message_id.strip()
            if message_id:
                overrides[message_id] = label.strip()

    store = GmailBatchReviewStore(args.storage_dir)
    batch = store.load_batch(args.batch_id)
    reviewed = []
    for item in batch["items"]:
        if item.get("review_state") == "reviewed":
            continue
        item["review_state"] = "reviewed"
        item["review_action"] = "codex-full-body-review"
        item["final_labels"] = [overrides.get(item["message_id"], args.default_label)]
        reviewed.append(item)
    unknown = sorted(set(overrides).difference({item["message_id"] for item in reviewed}))
    if unknown:
        raise ValueError(f"Override ids are not pending in {args.batch_id}: {', '.join(unknown)}")
    store.persist_reviewed_items(args.batch_id, batch["items"])

    if args.local_only:
        print(f"Reviewed: {len(reviewed)}")
        print("Gmail labels applied: 0 (local-only)")
        return 0

    gmail_client = default_gmail_client_factory(
        batch["account_id"],
        args.credentials_dir,
        args.client_secret_path,
        GMAIL_MODIFY_SCOPE,
    )
    summary = build_gmail_label_writer(gmail_client, args.storage_dir).write_reviewed_labels(args.batch_id, reviewed)
    print(f"Reviewed: {len(reviewed)}")
    print(f"Gmail labels applied: {summary['applied_count']}")
    print(f"Failed: {summary['failed_count']}")
    print(f"Skipped: {summary['skipped_count']}")
    return 0 if summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
