"""
Agent A — CSV ingest and $1 deletion.

Pipeline order (see contract/PIPELINE.md)::

    ingest → delete_$1 → clean → (aggregate/roll_up owned by Agent D)

Public entrypoints
------------------
- ``load_config`` — read ``config/defaults.yaml``
- ``ingest_directory`` — load CSVs; reject credential-like columns
- ``apply_delete_amounts`` — exact DELETE_AMOUNTS filter; write deleted_records.txt
- ``run_pipeline`` — full ingest → delete → clean → ``NormalizedBundle`` + findings
- ``build_normalized_bundle`` — bundle-only convenience wrapper

Roll-up policy: Final-sheet ``AGGREGATE BELOW THRESHOLD`` / ``WITHHELD`` rows are
kept with ``is_rollup=True`` for Agent B; ``rollups=[]`` until Agent D rebuilds.
"""

from src.ingest.config import load_config, repo_root
from src.ingest.deletion import DeletionResult, apply_delete_amounts
from src.ingest.loader import (
    CredentialColumnError,
    MissingInputError,
    RawIngest,
    ingest_directory,
)
from src.ingest.pipeline import PipelineResult, build_normalized_bundle, run_pipeline

__all__ = [
    "CredentialColumnError",
    "DeletionResult",
    "MissingInputError",
    "PipelineResult",
    "RawIngest",
    "apply_delete_amounts",
    "build_normalized_bundle",
    "ingest_directory",
    "load_config",
    "repo_root",
    "run_pipeline",
]
