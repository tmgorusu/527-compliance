"""CLI smoke tests — structure works even when siblings are incomplete."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cli.main import main
from src.cli.siblings import sibling_status


def test_cli_status_exits(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["status"])
    captured = capsys.readouterr()
    assert "agent_a_ingest_clean" in captured.out
    assert code in (0, 1)


def test_cli_run_missing_inputs(tmp_path: Path) -> None:
    code = main(
        [
            "run",
            "--jurisdiction",
            "federal",
            "--inputs",
            str(tmp_path / "nope"),
            "--output",
            str(tmp_path / "out"),
        ]
    )
    assert code == 2


def test_cli_run_graceful_when_siblings_missing(
    tmp_path: Path, fixtures_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status = sibling_status()
    inputs = fixtures_dir / "edge_cases" / "dollar_one"
    out = tmp_path / "out"
    code = main(
        [
            "run",
            "--jurisdiction",
            "federal",
            "--inputs",
            str(inputs),
            "--output",
            str(out),
        ]
    )
    captured = capsys.readouterr()
    if not status["agent_a_ingest_clean"]:
        assert code == 1
        assert "Sibling module unavailable" in captured.out or "ERROR" in captured.out
    else:
        # A present — may still fail later in pipeline; just ensure it ran
        assert code in (0, 1)


def test_help_lists_run() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
