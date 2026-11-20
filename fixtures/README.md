# Fixtures (Agent E)

| Path | Purpose |
|------|---------|
| `federal/minimal_bundle.json` | Minimal valid `NormalizedBundle` for Agent B federal XML + XSD golden/smoke |
| `golden/deleted_records_*.txt` | Expected `deleted_records.txt` format snippets |
| `edge_cases/dollar_one/` | Schedule A/B/ledger rows at exactly `1.00` for DELETE_AMOUNTS |
| `edge_cases/unapplied_cash_zero/` | Zero-balance unapplied cash (drop) + nonzero (fold later) |
| `edge_cases/below_threshold/` | Contributors/vendors below $200 / $500 for roll-up |
| `edge_cases/bad_rows/` | Schema/type failures expected in `rejects.csv` |
| `edge_cases/state_zip/` | State `VA (Virginia)` and numeric / short ZIP quirks |

Real Final exports (no credentials): `inputs/vpf/`, `inputs/upf/`.
