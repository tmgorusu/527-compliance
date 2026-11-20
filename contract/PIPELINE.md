# Ordered pipeline contract

Shared by all agents. Implementation lives in owner directories; this file is the sequencing contract.

```
ingest
  → delete_$1
  → clean
  → aggregate / threshold
  → roll_up
  → compliance
  → build_xml (federal | texas plugin)
  → xsd_check (federal)
  → reconcile
  → report
```

| Step | Owner | Inputs | Outputs | Fail conditions |
|------|-------|--------|---------|-----------------|
| ingest | A | `/inputs/*.csv` | raw row dicts | Missing required files; credential-like columns |
| delete_$1 | A | raw rows + `DELETE_AMOUNTS` | surviving rows; `DeletedRecord[]`; `output/deleted_records.txt` | Never silent; always write file |
| clean | A | surviving rows | normalized records; `output/rejects.csv`; findings | Schema/type failures → reject with reason |
| aggregate / threshold | D | cleaned A/B + YTD config | records with aggregate_ytd + threshold flags | — |
| roll_up | D | thresholded records + cover address | `RollupRecord[]` merged into schedules | — |
| compliance | D | bundle | findings (ERROR/WARN/INFO) | ERROR may fail run per CLI policy; unexplained issues flagged |
| build_xml | B / C | `NormalizedBundle` | XML bytes | Texas: missing spec → refuse with exact missing list; Federal: A1 unset → refuse amount encode |
| xsd_check | B | XML + `spec/8872Schema.xsd` | pass / ERROR findings | Any XSD error fails federal run |
| reconcile | D | bundle + PL + deleted + XML totals | reconciliation report | Unexplained P&L difference fails run |
| report | E/CLI | all artifacts | console summary + paths | — |

## deleted_records.txt format

Each deleted row (plain text):

```text
DELETED | schedule | source_row | date | name | amount | reason
```

Then summary lines: count deleted, total dollars deleted, per-schedule breakdown.  
If none: single line `NO RECORDS DELETED`.

Console prints the same summary.

## Agent fixture rule

Agent B builds/validates against `fixtures/`, not against Agent A’s live code. Agent E owns golden files.
