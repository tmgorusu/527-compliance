# Phase 1 Ambiguities — decisions required before Phase 2

Legend: **BLOCKING** = cannot implement correctly without your answer. **NON-BLOCKING** = tool can proceed with a documented default; confirm or override.

## Phase 2 assumed defaults (2026-11-19)

User started Phase 2 without explicit answers. Locked in `config/defaults.yaml` — **override anytime**:

| ID | Assumed default |
|----|-----------------|
| A1 | `integer_cents` (`$250.00` → `25000` in XML) |
| A2 | `gte` (≥ $200 / ≥ $500) |
| A3 | Schedule B roll-up purpose = `WITHHELD` |
| A4 | Export **both** VPF and UPF Final tabs → `inputs/{vpf,upf}/`; never Filing Access |
| A5 | Client label `WITHHELD` + WARN citing IRS |
| A6 | Optional `is_unapplied_cash` column + substring match; no fail if unmarked |
| A7–A10 | As previously proposed |

---

---

## A1. Federal XML amount encoding — BLOCKING

`USAmountType` is `xsd:integer`. Client P&L and schedules use dollars-and-cents (e.g. `22666.74`). Style guide says Schedule A presentation has no decimals; Schedule B may show cents. **No previously accepted sample 8872 XML is in this repo.**

**Choose one:**

1. **Whole dollars** — round (or truncate?) to integer dollars in XML; track rounding residue as a reconciling line.
2. **Integer cents** — e.g. `$250.00` → `25000` in XML.
3. **Supply a sample** — provide a redacted XML file previously accepted by the IRS upload validator; we will match its encoding exactly.

Also specify rounding mode if (1): half-up vs truncate toward zero.

**Default if you do not answer:** none — federal XML builder stays blocked on amount serialization.

---

## A2. Threshold inclusivity — NON-BLOCKING (default proposed)

- IRS Instructions (Schedule A): itemize if aggregate YTD **at least $200**.
- IRS Instructions (Schedule B): itemize if aggregate YTD **at least $500**.
- Client style guide wording: “above $200” / “above $500”.

**Proposed default:** follow IRS → itemize when YTD **≥ 200** / **≥ 500**.

Confirm or override to strict `>`.

---

## A3. Schedule B roll-up `ExpenditurePurpose` — BLOCKING for XML validity

XSD requires `ExpenditurePurpose` (1–512 chars). Client roll-up line is named `WITHHELD` with office address; purpose is empty in the Final sheet for that row.

IRS non-disclosure line says enter `Withheld` as purpose as well. Client below-threshold practice may differ.

**Choose purpose text for the WITHHELD roll-up line**, e.g.:

- `WITHHELD`
- `AGGREGATE BELOW THRESHOLD`
- something else you specify

---

## A4. Input source for this build — BLOCKING for integration run

Repo contains two Excel workbooks (VPF and UPF), not `/inputs/*.csv`. Style guide lives inside the workbooks. A “Filing Access” sheet contains portal credentials — **must never be exported, logged, or committed.**

**Choose:**

1. Which organization(s) to build first: **VPF**, **UPF**, or **both**?
2. May Phase 2/3 export CSVs from the Final tabs into `/inputs/` (redacting Filing Access entirely)?
3. Should Draft tabs ever be used, or **Final only**?

**Credential hygiene:** rotate any passwords that lived in those workbooks; treat the sheets as compromised for sharing purposes.

---

## A5. Schedule B below-threshold label vs IRS vocabulary — NON-BLOCKING (WARN)

- Client + filed Final sheets: below-threshold Schedule B line = **`WITHHELD`**.
- IRS Instructions: below-threshold = **`Aggregate below Threshold`**; **`Withheld`** = amounts required to be reported but information withheld (penalty exposure).

**Proposed default:** emit client label `WITHHELD` per style guide; always raise a **WARN** finding citing IRS Instructions Schedule B (Non-Disclosed Amounts vs Aggregate below Threshold) for human review.

Confirm or override to IRS wording.

---

## A6. Unapplied cash identification — BLOCKING for that rule

Style guide: highlight unapplied cash bill payments in RED in Raw QBO; delete zero balances; fold final unapplied amount into WITHHELD.

Excel color highlighting does not survive CSV export.

**How should the tool identify unapplied-cash rows?** Options:

1. Optional column `is_unapplied_cash` on `schedule_b.csv` / `raw_ledger.csv`.
2. Optional `unapplied_cash.csv` list of source row ids / amounts.
3. Name/description pattern you specify (provide exact strings).
4. Defer rule until you supply a marker convention.

---

## A7. Cover `report_type` data quality — NON-BLOCKING

UPF Cover Page shows period Jul–Sep 2026 but `Type of Report` = `Second quarterly` (Q2). VPF correctly has `Third quarterly` for the same period pattern.

**Proposed default:** trust `cover.csv` as authoritative; emit WARN if report type is inconsistent with period months; do not auto-correct.

---

## A8. YTD inputs — NON-BLOCKING (default proposed)

Aggregate YTD may come from (a) values already on Schedule A/B rows, (b) recalculation from YTD vendor/contribution feeds, or (c) both with mismatch → ERROR.

**Proposed default:** recalculate YTD from provided period rows + optional prior-period YTD file if present; if input `Aggregate Contributions YTD` / vendor YTD disagrees beyond $0.00, emit ERROR finding and fail compliance unless `--trust-input-ytd` is set.

Do you have a prior-period YTD extract, or should YTD on the Final sheet be trusted as already correct?

---

## A9. Texas priority — NON-BLOCKING

Confirm Texas remains skeleton-only until you drop official TEC spec into `spec/texas/`. No further Texas questions until then.

---

## A10. Multi-filing-type checkboxes — NON-BLOCKING

XSD `FilingType` uses `xsd:all` with optional 0/1 elements (multiple could be set). Cover dropdown is a single value.

**Proposed default:** set exactly one filing-type child to `1` from `cover.filing_type`; omit others (or set `0` — confirm preference). Amended + Change of Address simultaneously would require an explicit cover convention if you ever need both.
