"""FastAPI backend for 527 compliance — wraps the existing CLI pipeline.

Accepts Final-tab CSVs and/or client .xlsx workbooks.
Never accepts or stores portal credentials. Output artifacts only.
"""

from __future__ import annotations

import base64
import sys
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BACKEND_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_ROOT.parent

# Prefer vendored packages inside backend/ (Vercel service root), else repo root (local).
for candidate in (BACKEND_ROOT, REPO_ROOT):
    if (candidate / "src").is_dir() and (candidate / "contract").is_dir():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        CONFIG_PATH = candidate / "config" / "defaults.yaml"
        break
else:
    raise RuntimeError("Cannot locate src/ and contract/ for pipeline imports")

from src.cli.pipeline import run_pipeline  # noqa: E402
from src.ingest.excel_workbook import workbook_to_inputs  # noqa: E402

REQUIRED_FILES = {
    "cover.csv",
    "schedule_a.csv",
    "schedule_b.csv",
    "pl.csv",
}
OPTIONAL_FILES = {
    "vendor_list.csv",
    "vendor_ytd_totals.csv",
    "raw_ledger.csv",
    "exceptions.csv",
}
ALLOWED_CSV = REQUIRED_FILES | OPTIONAL_FILES
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}
FORBIDDEN_SUBSTRINGS = ("password", "username", "secret", "credential", "login")

Jurisdiction = Literal["federal", "texas", "both"]

app = FastAPI(
    title="527 Compliance API",
    description=(
        "CSV or Excel workbook → IRS Form 8872 XML. "
        "Humans upload portal files; this API never handles credentials."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class FindingOut(BaseModel):
    id: str
    severity: str
    rule: str
    sheet: str | None = None
    row: int | None = None
    field: str | None = None
    message: str
    source: str


class RunResponse(BaseModel):
    ok: bool
    jurisdiction: str
    error: str | None = None
    findings: list[FindingOut] = Field(default_factory=list)
    reconciliation: str | None = None
    deleted_records: str | None = None
    deleted_count: int = 0
    deleted_total: str | None = None
    federal_xml_base64: str | None = None
    federal_xml_filename: str = "form_8872.xml"
    schedule_a_count: int | None = None
    schedule_b_count: int | None = None
    ein: str | None = None
    organization_name: str | None = None
    source_files: list[str] = Field(default_factory=list)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "527-compliance"}


@app.get("/api/status")
def status() -> dict[str, object]:
    from src.cli.siblings import sibling_status

    return {"siblings": sibling_status(), "config": str(CONFIG_PATH)}


def _safe_name(name: str) -> str:
    return Path(name).name.lower().replace(" ", "_")


def _reject_credential_name(name: str) -> None:
    lower = name.lower()
    for token in FORBIDDEN_SUBSTRINGS:
        if token in lower:
            raise HTTPException(
                status_code=400,
                detail=f"Refused file or field matching credential pattern: {name!r}",
            )


@app.post("/api/run", response_model=RunResponse)
async def run(
    jurisdiction: Jurisdiction = Form("federal"),
    files: list[UploadFile] = File(...),
) -> RunResponse:
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Upload Final-tab CSVs and/or a client .xlsx workbook.",
        )

    with tempfile.TemporaryDirectory(prefix="527web_") as tmp:
        inputs = Path(tmp) / "inputs"
        output = Path(tmp) / "output"
        uploads = Path(tmp) / "uploads"
        inputs.mkdir()
        output.mkdir()
        uploads.mkdir()

        seen: set[str] = set()
        source_files: list[str] = []

        for upload in files:
            raw_name = upload.filename or ""
            _reject_credential_name(raw_name)
            safe = _safe_name(raw_name)
            suffix = Path(safe).suffix.lower()
            data = await upload.read()

            if suffix in EXCEL_SUFFIXES:
                xlsx_path = uploads / Path(safe).name
                xlsx_path.write_bytes(data)
                try:
                    written = workbook_to_inputs(xlsx_path, inputs)
                except Exception as exc:  # noqa: BLE001 — API boundary
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to read workbook {raw_name!r}: {exc}",
                    ) from exc
                seen.update(written)
                source_files.append(Path(raw_name).name)
                continue

            # CSV path
            name = safe if safe in ALLOWED_CSV else Path(safe).name
            if name not in ALLOWED_CSV:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unexpected file {raw_name!r}. "
                        f"Allowed CSVs: {sorted(ALLOWED_CSV)}; "
                        "or upload a client .xlsx workbook."
                    ),
                )
            _reject_credential_name(name)
            try:
                head = data[:4000].decode("utf-8", errors="replace").splitlines()[:1]
                if head:
                    _reject_credential_name(head[0])
            except Exception:
                pass
            (inputs / name).write_bytes(data)
            seen.add(name)
            source_files.append(Path(raw_name).name)

        missing = REQUIRED_FILES - seen
        if missing:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Missing required inputs after import: {sorted(missing)}. "
                    "Upload the four CSVs, or an .xlsx with Cover Page / "
                    "Schedule A Final / Schedule B Final / PL sheets."
                ),
            )

        result = run_pipeline(
            jurisdiction=jurisdiction,
            inputs=inputs,
            output=output,
            config_path=CONFIG_PATH if CONFIG_PATH.exists() else None,
            fail_on_compliance_error=True,
        )

        findings = [
            FindingOut(
                id=f.id,
                severity=f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                rule=f.rule,
                sheet=f.sheet,
                row=f.row,
                field=f.field,
                message=f.message,
                source=f.source,
            )
            for f in result.findings
        ]

        deleted_text = None
        deleted_path = result.output_paths.get("deleted_records")
        if deleted_path and Path(deleted_path).exists():
            deleted_text = Path(deleted_path).read_text(encoding="utf-8")

        xml_b64 = None
        if result.federal_xml:
            xml_b64 = base64.b64encode(result.federal_xml).decode("ascii")

        cover = result.bundle.cover if result.bundle else None
        deleted_rows = result.bundle.deleted if result.bundle else []
        deleted_total = None
        if deleted_rows:
            from decimal import Decimal

            deleted_total = f"{sum((Decimal(d.amount) for d in deleted_rows), Decimal('0.00')):.2f}"
        return RunResponse(
            ok=result.ok,
            jurisdiction=result.jurisdiction,
            error=result.error,
            findings=findings,
            reconciliation=result.reconciliation_text,
            deleted_records=deleted_text,
            deleted_count=len(deleted_rows),
            deleted_total=deleted_total,
            federal_xml_base64=xml_b64,
            schedule_a_count=len(result.bundle.schedule_a) if result.bundle else None,
            schedule_b_count=len(result.bundle.schedule_b) if result.bundle else None,
            ein=cover.ein if cover else None,
            organization_name=cover.organization_name if cover else None,
            source_files=source_files,
        )
