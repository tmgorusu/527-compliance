# 527 Compliance Tool — Phase 1 Contract Spec

**Status:** Phase 1 — awaiting human approval before Phase 2  
**Jurisdictions:** `federal_irs_8872` (full), `texas_tec` (skeleton only)  
**Source of truth (federal):** `spec/8872Schema.xsd` + `spec/8871and8872Common.xsd` (IRS December 2012 / Version 2.3)  
**Instructions cited:** IRS Instructions for Form 8872 (Rev. October 2020), Pub. 4216  
**Client process rules:** `inputs/style_guide.md` (extracted from workbook; not law)

---

## 1. Scope and non-goals

### In scope
- Convert normalized CSV inputs into filing-ready **IRS Form 8872 XML** for federal.
- Apply client cleaning / threshold / roll-up / $1-deletion / P&L reconciliation rules.
- Emit advisory findings; produce reconciliation + `deleted_records.txt`.
- Texas plugin skeleton that **refuses** final XML until official TEC spec is present.

### Explicit non-goals
- The tool **never** decides whether an organization is required to file in any jurisdiction.
- The tool **never** reads, stores, logs, or transmits portal credentials. Output files only; a human uploads.
- The tool does **not** invent Texas element names, form numbers, thresholds, or deadlines.
- Findings are advisory; a human files.

---

## 2. Directory ownership (agents edit only their dirs)

| Path | Owner |
|------|--------|
| `spec/`, `contract/`, `config/` | Agent 0 (contract) — this phase |
| `src/ingest/`, `src/cleaning/` | Agent A |
| `src/xmlbuild/federal/` | Agent B |
| `src/xmlbuild/texas/` | Agent C |
| `src/compliance/` | Agent D |
| `src/cli/`, `tests/`, `fixtures/` | Agent E |
| `inputs/` | Human-supplied (or export script under Agent E with credential redaction) |
| `output/` | Runtime only (gitignored) |

Cross-directory needs go through `contract/*.schema.json` and this SPEC. Integration (Phase 3) may fix owner files to resolve interface mismatches.

---

## 3. Ordered pipeline

```
1. ingest          CSV → raw row objects (jurisdiction-independent)
2. delete_$1       exact-match DELETE_AMOUNTS; write deleted_records.txt; WARN sign-off
3. clean           normalize state/ZIP/whitespace/ALL CAPS; FLAG typos; rejects file
4. aggregate       YTD per contributor/vendor (post-deletion); threshold status
5. roll_up         AGGREGATE BELOW THRESHOLD (A) / WITHHELD (B); unapplied cash rules
6. compliance      date-in-period, cover totals, near-duplicates, amended WARN, findings
7. build_xml       federal (and texas if unblocked); plugin interface
8. xsd_check       validate federal XML against IRS XSD; fail loudly
9. reconcile       P&L tie-out; deletions as labeled reconciling lines; fail if unexplained
10. report         reconciliation report + findings; console summary of deletions
```

CLI: `--jurisdiction federal|texas|both`. Shared steps 1–6 and 9–10 are jurisdiction-independent. Step 7–8 are jurisdiction-specific.

Determinism: same inputs → byte-identical outputs (stable sort keys documented in §8).

---

## 4. Federal XSD element ↔ column / field mapping

Namespace: `http://forms.irs.gov/pofd/schema`  
Root: `FORM8872`  
Attributes (`pacInfo`): `ein` (positiveInteger, optional), `pacId` (positiveInteger, optional)

### 4.1 Header / cover (`CoverRecord` → `FORM8872`)

| XSD element / attr | Type / constraint | Source (cover.csv / CoverRecord) | Notes |
|--------------------|-------------------|----------------------------------|-------|
| `@ein` | positiveInteger | `ein` | 9 digits, no dash. Org name is **not** an XML element (cover note + XSD). |
| `@pacId` | positiveInteger | `pac_id` optional | Omit if unknown. |
| `MailingAddress` | `USAddressType` | `mailing_*` | |
| `FilingType/InitialReport` | 0\|1 int | `filing_type=initial` | Emit checked box as `1` when selected. |
| `FilingType/ChangeOfAddress` | 0\|1 | `filing_type=change_of_address` | |
| `FilingType/AmendedReport` | 0\|1 | `filing_type=amended` | Client Q3 files use Amended. |
| `FilingType/FinalReport` | 0\|1 | `filing_type=final` | |
| `DateEstablished` | `xsd:date` CCYY-MM-DD | `date_established` | |
| `eMail` | EmailAddressType 7–150 | `email` | |
| `CustodianName` | StringType 1–50 | `custodian_name` | |
| `CustodianAddress` | USAddressType | `custodian_*` | |
| `ContactPerson` | StringType 1–50 | `contact_name` | |
| `ContactAddress` | USAddressType | `contact_*` | |
| `BusinessAddress` | USAddressType | `business_*` | Also used for roll-up line address. |
| `PeriodBeginDate` | DateType | `period_begin` | |
| `PeriodEndDate` | DateType | `period_end` | |
| `ReportType/*` | choice | `report_type` + election fields | Exactly one branch. Map: first_quarterly→`FirstQuarterlyReport`, second→`SecondQuarterlyReport`, third→`ThirdQuarterlyReport`, year_end→`YearEndReport`, mid_year→`MidYearReport`, monthly→`MonthlyReport` (MM), pre_election→`PreElectionReport`, post_general→`PostGeneralElectionReport`. Checkbox string values are `"1"`. |

### 4.2 Address (`USAddressType`)

| XSD | Constraint | Normalized field |
|-----|------------|------------------|
| `AddressLine1` | StreetAddressType max 35 | `address_line1` |
| `AddressLine2` | optional max 35 | `address_line2` |
| `City` | CityType max 22 | `city` |
| `State` | 2-letter StateType | `state` |
| `ZIP5` | `[0-9]{5}` | `zip5` |
| `ZIP4` | optional nillable `[0-9]{4}` | `zip4` |

### 4.3 Schedule A (`SCHEDULEA` or `NoScheduleA`)

| XSD | Source (`ScheduleARecord`) | Notes |
|-----|----------------------------|-------|
| `ContributorName` | `name` | Roll-up: `AGGREGATE BELOW THRESHOLD` (client). IRS also defines `Withheld` for non-disclosure penalty lines — see ambiguities. |
| `ContributorAddress` | address fields | Roll-up uses org business/office address from cover. |
| `ContributorEmployer` | `employer` | Roll-up: `N/A` per IRS instructions. `BEST EFFORTS MADE` / `N/A` valid placeholders. |
| `ContributorOccupation` | `occupation` | Roll-up: `N/A`. |
| `ContributionDate` | `date` | Roll-up: period end date (IRS: last day of reporting period). |
| `ContributionAmount` | `amount` → XML integer | See **blocking ambiguity A1** (cents vs whole dollars). |
| `AggregateContributionsYTD` | `aggregate_ytd` → XML integer | Same amount encoding as above. |

IRS itemization rule (Instructions for Form 8872, Schedule A): list each contributor if aggregate contributions during the calendar year as of period end were **at least $200** and any were accepted during the period. Client style guide says “above $200”; contract default follows IRS **≥ $200** unless human overrides (ambiguity A2).

### 4.4 Schedule B (`SCHEDULEB` or `NoScheduleB`)

| XSD | Source (`ScheduleBRecord`) | Notes |
|-----|----------------------------|-------|
| `RecipientName` | `name` | Client below-threshold roll-up name: `WITHHELD`. IRS below-threshold label is `Aggregate below Threshold`; `Withheld` is the non-disclosure line (penalty). Client rule wins for process; emit WARN citing IRS. |
| `RecipientAddress` | address fields | Roll-up: org office address. |
| `RecipientEmployer` | `employer` | Often `N/A`. |
| `RecipientOccupation` | `occupation` | Often `N/A`. |
| `ExpenditureDate` | `date` | |
| `ExpenditureAmount` | `amount` → XML integer | Same encoding as Schedule A (A1). |
| `ExpenditurePurpose` | `purpose` | Required 1–512. Client roll-up purpose TBD if empty — see A3. |

IRS itemization: aggregate expenditures to person during calendar year as of period end **at least $500**, with any expenditure in period. Contract default **≥ $500** (ambiguity A2).

### 4.5 Amount encoding (OPEN — blocking)

`USAmountType` is `xsd:integer`. Paper Form 8872 and client P&L use dollars-and-cents. **No accepted sample XML is in-repo.** Phase 2 federal builder must not guess. Options for human decision: see Ambiguity **A1**.

Internal normalized records store amounts as **decimal dollars with 2 fractional digits** (`Decimal` / string `"1234.56"`) so reconciliation ties to P&L. XML conversion is isolated to the federal builder once A1 is decided.

---

## 5. Texas (`texas_tec`) — TBD mapping

**Do not invent.** Plugin refuses to emit final XML until an official TEC filing spec/format file is present under `spec/texas/` (path configurable).

### Exactly what the human must supply

1. **Official TEC filing format** for the applicable report (PDF + machine schema if any: XSD, JSON Schema, CSV template, or EDI).
2. **Root document / form identifier** and version (form number, revision date).
3. **Element or field names** for: filer identity, period, contribution schedule, expenditure schedule, address, amounts, dates.
4. **Date format** required by TEC.
5. **Amount format** (decimals allowed? cents? whole dollars?).
6. **Thresholds and aggregation rules** TEC requires (do not reuse IRS $200/$500 without TEC source).
7. **Character set / case / encoding** rules.
8. **Sample accepted filing file** (redacted) if available.
9. **Filing deadline / period rules** only if the tool must validate them (otherwise leave to human).
10. Confirmation whether Texas uses the **same CSV inputs** or a different extract.

Until then, Agent C delivers: plugin interface, mapping table stubs marked `TBD`, tests that assert refusal message lists the missing items above.

---

## 6. Client process rules (implemented in code; not legal conclusions)

Source: workbook “Instructions and Style Guide” → `inputs/style_guide.md`.

1. Schedule A: itemize when YTD aggregate ≥ threshold; else one line `AGGREGATE BELOW THRESHOLD` with client office address.
2. Schedule B: itemize when YTD aggregate ≥ threshold; else one line `WITHHELD` with client office address.
3. Unapplied cash bill payments: drop zeros; disclose nonzero; fold final unapplied-cash amount into `WITHHELD`.
4. Schedule A/B totals must reconcile to P&L revenue/expenses; unexplained difference → fail run.
5. Output text ALL CAPS (header rows excepted). Schedule A presentation: no `$` or decimals. Schedule B presentation: no `$`.
6. Unanimous-consent exceptions only from optional `exceptions.csv`; never assume present.

### $1 deletion rule (before thresholds / aggregation / roll-ups)

- Config: `config/defaults.yaml` → `DELETE_AMOUNTS: ["1.00"]` (exact Decimal match; never hardcode in logic).
- Applies to Schedule A, Schedule B, and raw ledger rows when those inputs are present.
- Every deleted row → `/output/deleted_records.txt`:
  `DELETED | schedule | source_row | date | name | amount | reason`
- File always exists; if none deleted: `NO RECORDS DELETED`.
- Summary (count, total dollars, per schedule) appended to file and printed to console.
- Deleted dollars appear as labeled reconciling line(s) in P&L reconciliation.
- Flag contributors/vendors whose threshold status changes because of deletions.
- WARN finding: deletion requires human sign-off.

---

## 7. Input CSV contracts

Expected under `inputs/` (or path via CLI):

| File | Role |
|------|------|
| `cover.csv` | Flat single-row cover fields (§4.1 column names, snake_case). |
| `schedule_a.csv` | Headers matching Schedule A Final. |
| `schedule_b.csv` | Headers matching Schedule B Final. |
| `pl.csv` | P&L lines: at minimum `line_label,amount` (plus optional `section`). |
| `vendor_list.csv` | Vendor contact / address reference. |
| `vendor_ytd_totals.csv` | Vendor YTD totals for threshold cross-check. |
| `exceptions.csv` | Optional unanimous-consent exceptions. |
| `style_guide.md` | Human reference (not parsed as law). |
| `raw_ledger.csv` | Optional; raw QBO for unapplied-cash / $1 deletion on ledger. |

**Credential ban:** never export or ingest a “Filing Access” sheet. Columns named password/username/secret are rejected at ingest.

Current repo has Excel workbooks only (VPF + UPF). CSV export is Phase 2/3 after Ambiguity **A4**.

---

## 8. Determinism

- Sort Schedule A by `(date, name, address_line1, amount, source_row)`.
- Sort Schedule B by `(date, name, purpose, amount, source_row)`.
- Roll-up lines last within each schedule.
- XML: fixed attribute order per XSD sequence; UTF-8; consistent indentation (2 spaces); no timestamps in payload.
- Decimal quantization: `ROUND_HALF_UP` to 2 places for internal money **unless** A1 dictates otherwise for XML only.

---

## 9. Outputs

| Path | Contents |
|------|----------|
| `output/form_8872.xml` | Federal XML (when jurisdiction includes federal) |
| `output/texas_filing.*` | Blocked until TEC spec |
| `output/deleted_records.txt` | Always |
| `output/rejects.csv` | Ingest/clean rejects with reasons |
| `output/findings.json` | Array of Finding objects |
| `output/reconciliation_report.txt` | Counts/dollars: input → after deletions → after roll-ups → XML; P&L tie-out |

---

## 10. Plugin interface (conceptual)

```text
JurisdictionPlugin
  id: str                          # federal_irs_8872 | texas_tec
  required_spec_files() -> list    # empty if ready
  build(normalized_bundle) -> bytes | raise SpecMissingError(missing=[...])
  validate(payload) -> list[Finding]
```

---

## 11. Ambiguities requiring human decision

See `spec/AMBIGUITIES.md`. **Phase 2 must not start until blocking items are resolved.**
