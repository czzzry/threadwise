import argparse
from pathlib import Path

from src.hotspot_sender_memory_backfill import backfill_hotspot_sender_memory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill sender-wide memory for applied hotspot founder answers.")
    parser.add_argument("--output-storage-dir", type=Path, required=True)
    parser.add_argument("--gmail-storage-dir", type=Path, required=True)
    parser.add_argument("--protonmail-storage-dir", type=Path, required=True)
    parser.add_argument("--outlookmail-storage-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = backfill_hotspot_sender_memory(
        args.output_storage_dir,
        [
            ("gmail", args.gmail_storage_dir),
            ("protonmail", args.protonmail_storage_dir),
            ("outlookmail", args.outlookmail_storage_dir),
        ],
    )
    print(
        f"Hotspot sender-memory backfill: applications={result['processed_application_count']} "
        f"| proposals={len(result['created_proposal_ids'])} | rules={len(result['created_rule_ids'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
