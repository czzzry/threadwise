from pathlib import Path
import argparse
import shutil
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from src.gmail_companion_ui import main as run_companion_main


DEFAULT_SOURCE_STORAGE_DIR = Path("examples/gmail_companion_demo")
DEFAULT_SIMULATOR_STORAGE_DIR = Path("data/gmail_companion_simulator")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare and serve a safe local inbox simulator for the Gmail companion."
    )
    parser.add_argument("--source-storage-dir", type=Path, default=DEFAULT_SOURCE_STORAGE_DIR)
    parser.add_argument("--simulator-storage-dir", type=Path, default=DEFAULT_SIMULATOR_STORAGE_DIR)
    parser.add_argument("--batch-limit", type=int, default=4)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8031)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    prepare_simulator_storage(
        source_storage_dir=args.source_storage_dir,
        simulator_storage_dir=args.simulator_storage_dir,
        batch_limit=args.batch_limit,
    )
    return run_companion_main(
        [
            "--storage-dir",
            str(args.simulator_storage_dir),
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--disable-gmail-write-through",
            "--disable-gmail-check",
        ]
    )


def prepare_simulator_storage(
    *,
    source_storage_dir: Path,
    simulator_storage_dir: Path,
    batch_limit: int,
) -> None:
    if simulator_storage_dir.exists():
        shutil.rmtree(simulator_storage_dir)
    (simulator_storage_dir / "batches").mkdir(parents=True, exist_ok=True)
    (simulator_storage_dir / "reports").mkdir(parents=True, exist_ok=True)

    source_batches_dir = source_storage_dir / "batches"
    batch_paths = sorted(source_batches_dir.glob("*.json"))[-batch_limit:] if source_batches_dir.exists() else []
    copied_batch_ids: list[str] = []
    for batch_path in batch_paths:
        destination = simulator_storage_dir / "batches" / batch_path.name
        shutil.copy2(batch_path, destination)
        copied_batch_ids.append(batch_path.stem)

    for batch_id in copied_batch_ids:
        for suffix in (
            "_write_status.json",
            "_inbox_removal_status.json",
            "_write_attempts.json",
            "_inbox_removal_attempts.json",
            "_fetch_failures.json",
        ):
            source_path = source_storage_dir / f"{batch_id}{suffix}"
            if source_path.exists():
                shutil.copy2(source_path, simulator_storage_dir / source_path.name)

        report_path = source_storage_dir / "reports" / f"{batch_id}_daily_report.json"
        if report_path.exists():
            shutil.copy2(report_path, simulator_storage_dir / "reports" / report_path.name)

    for shared_name in (
        "teachable_classification_rules.json",
        "memory_proposals.json",
        "unsubscribe_inventory.json",
        "unsubscribe_execution_log.json",
        "unsubscribe_manual_followups.json",
    ):
        source_path = source_storage_dir / shared_name
        if source_path.exists():
            shutil.copy2(source_path, simulator_storage_dir / shared_name)


if __name__ == "__main__":
    raise SystemExit(main())
