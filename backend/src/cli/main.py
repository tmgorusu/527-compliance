"""CLI: ``python -m src.cli run --jurisdiction … --inputs … --output …``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.cli.pipeline import run_pipeline
from src.cli.siblings import sibling_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compliance527",
        description=(
            "527 political organization CSV → filing-ready XML "
            "(IRS 8872 / Texas TEC plugin). Never reads portal credentials."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the ordered compliance pipeline")
    run.add_argument(
        "--jurisdiction",
        required=True,
        choices=("federal", "texas", "both"),
        help="Which jurisdiction plugin(s) to build",
    )
    run.add_argument(
        "--inputs",
        required=True,
        type=Path,
        help="Directory containing cover/schedule_a/schedule_b/pl CSVs",
    )
    run.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory for XML, deleted_records, findings, etc.",
    )
    run.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional YAML override merged onto config/defaults.yaml",
    )
    run.add_argument(
        "--no-fail-on-compliance-error",
        action="store_true",
        help="Continue to XML even when compliance emits ERROR findings",
    )

    status = sub.add_parser(
        "status",
        help="Show which sibling agent modules are importable",
    )
    status.add_argument(
        "--quiet",
        action="store_true",
        help="Exit 0 if all core siblings present; else 1 (no banner)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "status":
        status = sibling_status()
        if not args.quiet:
            print("Sibling module status:")
            for key, ok in sorted(status.items()):
                print(f"  {'OK' if ok else 'MISSING':7} {key}")
        return 0 if all(status.values()) else 1

    if args.command == "run":
        if not args.inputs.is_dir():
            print(f"ERROR: inputs directory not found: {args.inputs}", file=sys.stderr)
            return 2
        result = run_pipeline(
            jurisdiction=args.jurisdiction,
            inputs=args.inputs,
            output=args.output,
            config_path=args.config,
            fail_on_compliance_error=not args.no_fail_on_compliance_error,
        )
        return 0 if result.ok else 1

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
