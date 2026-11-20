# Tester access guide

**Site:** https://527-compliance.vercel.app  
**Access:** open the URL — no app password. IRS portal credentials stay with you.

## What to try first

1. Pick one organization you support.
2. From your Google Sheet-to-XML build, export **.xlsx** (or the Cover / Schedule A Final / Schedule B Final / PL CSVs).
3. On the site: open **Workspace**, upload that org only, jurisdiction **Federal**.
4. Run **Build filing package**.
5. Check **Upload cleanup** and download **Deleted records** — confirm sub-$1 expenses (and exact $1.00) were removed as expected.
6. Download **XML** + **Reconciliation**; skim findings.
7. Sign in to **that client’s** IRS Political Organization Filing and Disclosure account and upload the XML there. Repeat with a different client login for the next org — never reuse one IRS login across clients in this workflow.

## Designed around your notes

| Need | How the tool handles it |
|------|-------------------------|
| Sub-$1 expense cleanup at upload | `DELETE_STRICTLY_UNDER: 1.00` on Schedule B + ledger; exact `1.00` via `DELETE_AMOUNTS` on A/B/ledger. Logged for sign-off. |
| Separate IRS login per client | One org per run. Tool never asks for or stores IRS usernames/passwords. You upload XML in each portal yourself. |
| Google Sheet → XML | Upload Sheet export (.xlsx) or Final-tab CSVs; pipeline builds XSD-oriented Form 8872 XML. |

## What we need from you

- A real (or anonymized) test filing package for one org, or a short note if cleanup rules differ from “remove under $1 on expenses + exact $1.”
- Feedback on deleted-records log, recon, and whether the XML uploads cleanly in the IRS portal.
- When ready, filings for the organizations you support — same one-org-at-a-time flow.
