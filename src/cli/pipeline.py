"""Ordered pipeline orchestration (contract/PIPELINE.md)."""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from contract.models import Finding, FindingsDocument, NormalizedBundle, Severity

from src.cli.config_loader import load_config
from src.cli.deleted_report import console_summary, write_deleted_records
from src.cli.siblings import SiblingUnavailableError, require, resolve_siblings

Jurisdiction = Literal["federal", "texas", "both"]


@dataclass
class PipelineResult:
    ok: bool
    jurisdiction: Jurisdiction
    bundle: NormalizedBundle | None = None
    findings: list[Finding] = field(default_factory=list)
    federal_xml: bytes | None = None
    texas_payload: bytes | None = None
    reconciliation_text: str | None = None
    output_paths: dict[str, Path] = field(default_factory=dict)
    error: str | None = None


def _as_findings(raw: Any) -> list[Finding]:
    if raw is None:
        return []
    if isinstance(raw, FindingsDocument):
        return list(raw.findings)
    if isinstance(raw, list):
        out: list[Finding] = []
        for item in raw:
            if isinstance(item, Finding):
                out.append(item)
            elif isinstance(item, dict):
                out.append(Finding.model_validate(item))
        return out
    return []


def _call_agent_a(
    apis: Any, inputs: Path, output: Path, config: dict[str, Any]
) -> tuple[NormalizedBundle, list[Finding]]:
    """Invoke Agent A ``run_pipeline`` / ``build_normalized_bundle``."""
    if apis.run_ingest_pipeline is not None:
        result = apis.run_ingest_pipeline(
            inputs, output_dir=output, config=config
        )
        # Agent A PipelineResult dataclass
        if hasattr(result, "bundle"):
            findings = _as_findings(getattr(result, "findings", None))
            bundle = result.bundle
            if isinstance(bundle, dict):
                bundle = NormalizedBundle.model_validate(bundle)
            return bundle, findings
        if isinstance(result, NormalizedBundle):
            return result, []
        if isinstance(result, tuple) and result:
            bundle = result[0]
            findings = _as_findings(result[1]) if len(result) > 1 else []
            if isinstance(bundle, dict):
                bundle = NormalizedBundle.model_validate(bundle)
            return bundle, findings

    build_fn = require(
        apis.build_normalized_bundle,
        "src.ingest.run_pipeline / build_normalized_bundle (Agent A)",
    )
    bundle = build_fn(inputs, output_dir=output, config_path=None)
    # build_normalized_bundle does not accept config=; reload via config_path if needed
    if isinstance(bundle, dict):
        bundle = NormalizedBundle.model_validate(bundle)
    return bundle, []


def _write_findings(path: Path, findings: list[Finding]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = FindingsDocument(findings=findings)
    path.write_text(
        json.dumps(doc.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _failing_error_findings(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == Severity.ERROR]


def run_pipeline(
    *,
    jurisdiction: Jurisdiction,
    inputs: Path | str,
    output: Path | str,
    config_path: Path | str | None = None,
    fail_on_compliance_error: bool = True,
) -> PipelineResult:
    """
    Run the full ordered pipeline for the requested jurisdiction(s).

    Steps: ingest → delete_$1 → clean → aggregate/threshold → roll_up →
    compliance → build_xml → xsd_check → reconcile → report
    """
    inputs_dir = Path(inputs)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = PipelineResult(ok=False, jurisdiction=jurisdiction)
    findings: list[Finding] = []
    paths: dict[str, Path] = {}

    try:
        config = load_config(config_path)
        apis = resolve_siblings()

        if apis.run_ingest_pipeline is None and apis.build_normalized_bundle is None:
            raise SiblingUnavailableError(
                "Sibling module unavailable: src.ingest.run_pipeline / "
                "build_normalized_bundle (Agent A). "
                "Complete the owning agent package, then re-run."
            )

        # --- ingest → delete_$1 → clean (Agent A) ---
        bundle, a_findings = _call_agent_a(apis, inputs_dir, output_dir, config)
        findings.extend(a_findings)

        # Ensure deleted_records.txt always exists (A should write; we reinforce).
        deleted_name = (
            (config.get("OUTPUT") or {}).get("deleted_records_path")
            or "deleted_records.txt"
        )
        deleted_path = output_dir / Path(deleted_name).name
        write_deleted_records(deleted_path, bundle.deleted)
        paths["deleted_records"] = deleted_path
        print(console_summary(bundle.deleted))

        # --- aggregate / threshold → roll_up (Agent D) ---
        thr_fn = require(
            apis.apply_thresholds_and_rollups,
            "src.compliance.apply_thresholds_and_rollups (Agent D)",
        )
        bundle = thr_fn(bundle, config)
        if isinstance(bundle, dict):
            bundle = NormalizedBundle.model_validate(bundle)

        # --- compliance (Agent D) ---
        compliance_fn = require(
            apis.run_compliance,
            "src.compliance.run_compliance (Agent D)",
        )
        findings.extend(_as_findings(compliance_fn(bundle, config)))

        if fail_on_compliance_error and _failing_error_findings(findings):
            findings_path = output_dir / Path(
                (config.get("OUTPUT") or {}).get("findings_path")
                or "findings.json"
            ).name
            _write_findings(findings_path, findings)
            paths["findings"] = findings_path
            result.bundle = bundle
            result.findings = findings
            result.output_paths = paths
            result.error = "Compliance returned ERROR findings; aborting before XML."
            result.ok = False
            _print_report(result)
            return result

        # --- build_xml + xsd_check ---
        if jurisdiction in ("federal", "both"):
            build_fn = require(
                apis.build_form_8872,
                "src.xmlbuild.federal.build_form_8872 (Agent B)",
            )
            xml_bytes = build_fn(bundle, config)
            if isinstance(xml_bytes, str):
                xml_bytes = xml_bytes.encode("utf-8")
            result.federal_xml = xml_bytes

            validate_fn = require(
                apis.validate_form_8872,
                "src.xmlbuild.federal.validate_form_8872 (Agent B)",
            )
            validate_fn(xml_bytes)

            fed_name = (
                (config.get("OUTPUT") or {}).get("federal_xml_path")
                or "form_8872.xml"
            )
            fed_path = output_dir / Path(fed_name).name
            fed_path.write_bytes(xml_bytes)
            paths["federal_xml"] = fed_path

        if jurisdiction in ("texas", "both"):
            texas_build = require(
                apis.texas_build,
                "src.xmlbuild.texas plugin.build (Agent C)",
            )
            try:
                payload = texas_build(bundle)
                if isinstance(payload, str):
                    payload = payload.encode("utf-8")
                result.texas_payload = payload
                tex_path = output_dir / "texas_filing.bin"
                tex_path.write_bytes(payload)
                paths["texas_filing"] = tex_path
            except Exception as exc:  # SpecMissingError or incomplete plugin
                if apis.SpecMissingError and isinstance(exc, apis.SpecMissingError):
                    result.error = str(exc)
                    findings.append(
                        Finding(
                            id="TEX-SPEC-001",
                            severity=Severity.ERROR,
                            rule="texas_spec_missing",
                            sheet=None,
                            row=None,
                            field=None,
                            message=str(exc),
                            source="src.xmlbuild.texas",
                        )
                    )
                    if jurisdiction == "texas":
                        findings_path = output_dir / "findings.json"
                        _write_findings(findings_path, findings)
                        paths["findings"] = findings_path
                        result.bundle = bundle
                        result.findings = findings
                        result.output_paths = paths
                        result.ok = False
                        _print_report(result)
                        return result
                else:
                    raise

        # --- reconcile (Agent D) ---
        recon_fn = require(
            apis.reconcile,
            "src.compliance.reconcile (Agent D)",
        )
        recon_out = recon_fn(bundle, config)
        recon_ok = True
        if isinstance(recon_out, tuple):
            report_text = recon_out[0]
            if len(recon_out) > 1:
                findings.extend(_as_findings(recon_out[1]))
            if len(recon_out) > 2:
                recon_ok = bool(recon_out[2])
        else:
            report_text = str(recon_out)
        result.reconciliation_text = report_text

        recon_name = (
            (config.get("OUTPUT") or {}).get("reconciliation_path")
            or "reconciliation_report.txt"
        )
        recon_path = output_dir / Path(recon_name).name
        if apis.write_reconciliation_report is not None:
            apis.write_reconciliation_report(recon_path, report_text)
        else:
            recon_path.parent.mkdir(parents=True, exist_ok=True)
            recon_path.write_text(report_text, encoding="utf-8")
        paths["reconciliation"] = recon_path

        findings_path = output_dir / Path(
            (config.get("OUTPUT") or {}).get("findings_path") or "findings.json"
        ).name
        _write_findings(findings_path, findings)
        paths["findings"] = findings_path

        result.bundle = bundle
        result.findings = findings
        result.output_paths = paths
        result.ok = recon_ok and result.error is None
        if not recon_ok and result.error is None:
            result.error = "Reconciliation reported unexplained P&L difference."
        _print_report(result)
        return result

    except SiblingUnavailableError as exc:
        result.error = str(exc)
        result.findings = findings
        result.output_paths = paths
        print(f"ERROR: {exc}", flush=True)
        return result
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        result.error = f"{type(exc).__name__}: {exc}"
        result.findings = findings
        result.output_paths = paths
        print(f"ERROR: {result.error}", flush=True)
        traceback.print_exc()
        return result


def _print_report(result: PipelineResult) -> None:
    """Console summary + artifact paths (pipeline report step)."""
    print("--- pipeline report ---")
    print(f"jurisdiction: {result.jurisdiction}")
    print(f"ok: {result.ok}")
    if result.error:
        print(f"error: {result.error}")
    errors = sum(1 for f in result.findings if f.severity == Severity.ERROR)
    warns = sum(1 for f in result.findings if f.severity == Severity.WARN)
    print(f"findings: {len(result.findings)} (ERROR={errors}, WARN={warns})")
    for key, path in sorted(result.output_paths.items()):
        print(f"artifact[{key}]: {path}")
