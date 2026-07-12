import argparse
from pathlib import Path

from src.compiled_rule_rebuild import rebuild_compiled_rules


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild compiled accepted rules from approved memory proposals and accepted shadow suggestions.")
    parser.add_argument("--output-storage-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = rebuild_compiled_rules(args.output_storage_dir)
    print(
        f"Compiled rule rebuild: proposals={result['approved_proposal_count']} "
        f"| proposal-rules={result['proposal_rule_count']} | shadow-rules={result['shadow_rule_count']} "
        f"| total={result['total_rule_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
