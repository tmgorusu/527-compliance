# 527-compliance

End-to-end tool: CSV exports of 527 political organization data → filing-ready XML.

| Jurisdiction | Status |
|--------------|--------|
| Federal IRS Form 8872 | Filing-ready XML; validates against official XSD in `spec/` |
| Texas Ethics Commission | Plugin skeleton only until official TEC spec is supplied |

Sample inputs: `inputs/vpf`, `inputs/upf` (Final-tab exports; no credentials).  
Contract: `spec/SPEC.md`, `spec/AMBIGUITIES.md`.

## Website (Vercel)

Next.js UI in `frontend/` + FastAPI in `backend/` wrapping the same pipeline.

```bash
# Local API
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn backend.main:app --reload --port 8000

# Local UI (proxies /api → :8000)
cd frontend && npm install && npm run dev
```

Production: [https://527-compliance.vercel.app](https://527-compliance.vercel.app)

### Tester access (Kyle)

- **Link:** https://527-compliance.vercel.app — no app login.
- **Try first:** one client workbook (Google Sheet → File → Download → .xlsx, or Final-tab CSVs). Confirm Deleted records for sub-$1 / $1.00 cleanup, download XML, then upload in **that client’s** IRS Political Organization portal.
- **Designed around:** (1) sub-$1 expense cleanup at upload plus exact $1.00, (2) separate IRS login per client — never stored here, (3) Sheet/Excel → 8872 XML.
- Details: [TESTER.md](TESTER.md)

Before deploy, sync vendored Python into `backend/`:

```bash
bash scripts/sync_backend_vendor.sh
vercel --prod
```

(`vercel.json` runs Next.js + FastAPI as Vercel Services.)

## CLI

```bash
# Install (from repo root)
python -m pip install -e ".[dev]"

# Full pipeline (federal)
python -m src.cli run --jurisdiction federal --inputs ./inputs/vpf --output ./output/vpf

# Texas (refuses until TEC spec is present under spec/texas/)
python -m src.cli run --jurisdiction texas --inputs ./inputs/vpf --output ./output/texas

# Both
python -m src.cli run --jurisdiction both --inputs ./inputs/vpf --output ./output/both

# Optional config override (merged onto config/defaults.yaml)
python -m src.cli run --jurisdiction federal --inputs ./inputs/upf --output ./output/upf --config ./config/defaults.yaml

# Which sibling agent modules are importable
python -m src.cli status
```

Entry point script (after install): `compliance527 run …`

## Tests

```bash
pytest
# or focused:
pytest tests/test_deleted_records_format.py tests/test_fixtures.py
```

Fixtures (edge cases + federal minimal bundle + golden deleted_records) live under `fixtures/`.

## Human review checklist (before filing)

- [ ] Confirm the organization is required to file (tool does not decide).
- [ ] Review `output/findings.json` — especially WARN on $1 deletions and WITHHELD labeling.
- [ ] Sign off deletions in `output/deleted_records.txt`.
- [ ] Confirm reconciliation report ties Schedule A/B → P&L with only explained differences.
- [ ] Federal: XML validates against IRS XSD with zero errors.
- [ ] Upload XML via IRS portal yourself — never put portal credentials in this tool or repo.
- [ ] Texas: do not file tool output until TEC spec unlocks generation.

## Credentials

Never commit or feed Filing Access / portal passwords into this project. Output files only.

## Layout

See `spec/SPEC.md` §2 and `contract/PIPELINE.md`.
