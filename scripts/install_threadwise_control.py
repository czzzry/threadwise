from pathlib import Path
import argparse
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from src.threadwise_control_installer import install_control_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the Threadwise menu-bar service control.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = install_control_app(args.repo_root, dry_run=args.dry_run)
    if result["dry_run"]:
        print(f"Would install Threadwise Control at {result['app_path']}")
    else:
        print(f"Installed Threadwise Control at {result['app_path']}")
        print("The menu-bar control will open at login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
