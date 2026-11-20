# Texas TEC — required human spec drops

**Jurisdiction id:** `texas_tec`  
**Plugin:** `src/xmlbuild/texas/`  
**Rule:** Do not invent TEC element names, form numbers, thresholds, or deadlines.  
The Texas plugin **refuses** `build()` / `validate()` until the checklist below is satisfied.

This file is the plugin contract checklist (SPEC.md §5). Drop official materials into this directory (`spec/texas/`). Filenames below are what `TexasTecPlugin.required_spec_files()` expects.

---

## Exact filenames to drop

| # | Filename under `spec/texas/` | SPEC.md §5 item |
|---|------------------------------|-----------------|
| 1a | `tec_filing_format.pdf` | Official TEC filing format for the applicable report (PDF). |
| 1b | `tec_machine_schema.xsd` *(or `.json` / `.csv` / `.edi`)* **or** `tec_machine_schema.NONE` | Machine schema if any; use `.NONE` to document that none exists. |
| 2 | `form_identifier.txt` | Root document / form identifier and version (form number, revision date). |
| 3 | `field_names.md` | Element or field names for: filer identity, period, contribution schedule, expenditure schedule, address, amounts, dates. |
| 4 | `date_format.txt` | Date format required by TEC. |
| 5 | `amount_format.txt` | Amount format (decimals allowed? cents? whole dollars?). |
| 6 | `thresholds.txt` | Thresholds and aggregation rules TEC requires (do not reuse IRS $200/$500 without TEC source). |
| 7 | `charset_encoding.txt` | Character set / case / encoding rules. |
| 8 | `sample_accepted_filing.xml` *(or `.json` / `.csv` / `.txt` / `.bin`)* **or** `sample_accepted_filing.NONE` | Sample accepted filing file (redacted) if available; use `.NONE` if unavailable. |
| 9 | `filing_deadlines.txt` **or** `filing_deadlines.NONE` | Filing deadline / period rules only if the tool must validate them (otherwise leave to human — drop `.NONE`). |
| 10 | `input_csv_confirmation.txt` | Confirmation whether Texas uses the same CSV inputs or a different extract. |

---

## Notes for humans

- Prefer official TEC / Ethics Commission publications only. Do not paste guessed schemas.
- When a flexible item does not apply, create the corresponding `*.NONE` marker file with a one-line explanation (e.g. `No machine schema published by TEC for this report.`).
- After all rows above are satisfied, `required_spec_files()` returns `[]`. Emitting filing bytes still requires filling `mapping.py` from the dropped field-name materials — the skeleton will not invent TEC tags.
- `REQUIRED_SPEC.md` and `.gitkeep` are scaffolding; they do **not** unlock the plugin.

---

## Refusal behavior

Until the table is complete, `build(bundle)` and `validate(payload)` raise `SpecMissingError` whose `missing` list enumerates the unsatisfied SPEC.md §5 items (exact wording).
