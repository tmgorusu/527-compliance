"""
Agent A pipeline: ingest → delete_$1 → clean → NormalizedBundle.

Jurisdiction-independent. Never decides filing obligation.
Never logs or stores passwords / portal credentials.

Roll-up policy: keep Final-sheet AGGREGATE BELOW THRESHOLD / WITHHELD rows
with ``is_rollup=True`` for Agent B; leave ``rollups=[]`` for Agent D.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contract.models import Finding, NormalizedBundle

from src.cleaning.records import (
    clean_cover,
    clean_pl,
    clean_schedule_a,
    clean_schedule_b,
)
from src.cleaning.rejects import RejectCollector
from src.cleaning.unapplied import filter_unapplied_cash
from src.ingest.config import load_config
from src.ingest.deletion import apply_delete_amounts
from src.ingest.loader import RawIngest, ingest_directory


@dataclass
class PipelineResult:
    """Full Agent A output."""

    bundle: NormalizedBundle
    findings: list[Finding] = field(default_factory=list)
    raw: RawIngest | None = None
    rejects_path: Path | None = None
    deleted_records_path: Path | None = None
    reject_count: int = 0


def run_pipeline(
    inputs_dir: str | Path,
    *,
    output_dir: str | Path = "output",
    config_path: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> PipelineResult:
    """
    Public entrypoint: CSV ingest → $1 deletion → cleaning → NormalizedBundle.

    Always writes:
      - ``{output_dir}/deleted_records.txt`` (from config OUTPUT.deleted_records_path basename)
      - ``{output_dir}/rejects.csv``
    """
    cfg = config if config is not None else load_config(config_path)
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    deleted_name = Path(
        (cfg.get("OUTPUT") or {}).get("deleted_records_path", "output/deleted_records.txt")
    ).name
    deleted_path = out_root / deleted_name
    rejects_path = out_root / "rejects.csv"

    raw = ingest_directory(inputs_dir, cfg)

    deletion = apply_delete_amounts(
        schedule_a=raw.schedule_a,
        schedule_b=raw.schedule_b,
        raw_ledger=raw.raw_ledger,
        config=cfg,
        output_path=deleted_path,
    )

    rejects = RejectCollector()
    findings: list[Finding] = list(deletion.findings)

    # Unapplied cash: drop zeros with reason; flag nonzero (Schedule B + ledger).
    sched_b, _ = filter_unapplied_cash(
        deletion.schedule_b,
        sheet="schedule_b",
        amount_keys=("expenditure_amount", "amount"),
        config=cfg,
        rejects=rejects,
    )
    ledger, _ = filter_unapplied_cash(
        deletion.raw_ledger,
        sheet="raw_ledger",
        amount_keys=("amount",),
        config=cfg,
        rejects=rejects,
    )
    # Persist surviving ledger on raw for downstream consumers
    raw.raw_ledger = ledger

    cover = clean_cover(
        raw.cover, config=cfg, rejects=rejects, findings=findings
    )
    if cover is None:
        rejects.write_csv(rejects_path)
        raise ValueError(
            f"Cover record failed to clean; see rejects at {rejects_path}"
        )

    schedule_a = clean_schedule_a(
        deletion.schedule_a, config=cfg, rejects=rejects, findings=findings
    )
    schedule_b = clean_schedule_b(
        sched_b, config=cfg, rejects=rejects, findings=findings
    )
    pl_lines = clean_pl(raw.pl, config=cfg, rejects=rejects)

    rejects.write_csv(rejects_path)

    # Deterministic sort per SPEC §8; roll-ups last within each schedule.
    schedule_a = _sort_a(schedule_a)
    schedule_b = _sort_b(schedule_b)

    bundle = NormalizedBundle(
        cover=cover,
        schedule_a=schedule_a,
        schedule_b=schedule_b,
        deleted=deletion.deleted,
        rollups=[],  # Agent D owns roll-ups / thresholds
        pl_lines=pl_lines,
    )

    return PipelineResult(
        bundle=bundle,
        findings=findings,
        raw=raw,
        rejects_path=rejects_path,
        deleted_records_path=deleted_path,
        reject_count=len(rejects.rows),
    )


def build_normalized_bundle(
    inputs_dir: str | Path,
    *,
    output_dir: str | Path = "output",
    config_path: str | Path | None = None,
) -> NormalizedBundle:
    """Convenience: return only the NormalizedBundle (side-effect files still written)."""
    return run_pipeline(
        inputs_dir, output_dir=output_dir, config_path=config_path
    ).bundle


def _sort_a(rows: list) -> list:
    def key(r):
        return (
            1 if r.is_rollup else 0,
            r.date,
            r.name,
            r.address.address_line1,
            r.amount,
            r.source_row,
        )

    return sorted(rows, key=key)


def _sort_b(rows: list) -> list:
    def key(r):
        return (
            1 if r.is_rollup else 0,
            r.date,
            r.name,
            r.purpose,
            r.amount,
            r.source_row,
        )

    return sorted(rows, key=key)
