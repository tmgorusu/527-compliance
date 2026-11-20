"use client";

import { useMemo, useState } from "react";

type Jurisdiction = "federal" | "texas" | "both";

type Finding = {
  id: string;
  severity: string;
  rule: string;
  sheet: string | null;
  row: number | null;
  field: string | null;
  message: string;
  source: string;
};

type RunResponse = {
  ok: boolean;
  jurisdiction: string;
  error: string | null;
  findings: Finding[];
  reconciliation: string | null;
  deleted_records: string | null;
  deleted_count?: number;
  deleted_total?: string | null;
  federal_xml_base64: string | null;
  federal_xml_filename: string;
  schedule_a_count: number | null;
  schedule_b_count: number | null;
  ein: string | null;
  organization_name: string | null;
};

const REQUIRED_CSV = ["cover.csv", "schedule_a.csv", "schedule_b.csv", "pl.csv"] as const;
const OPTIONAL = [
  "vendor_list.csv",
  "vendor_ytd_totals.csv",
  "raw_ledger.csv",
  "exceptions.csv",
] as const;

function isExcelName(name: string) {
  const lower = name.toLowerCase();
  return lower.endsWith(".xlsx") || lower.endsWith(".xlsm");
}

function downloadBase64(b64: string, filename: string, mime: string) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const blob = new Blob([bytes], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadText(text: string, filename: string) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function severityStyles(severity: string) {
  if (severity === "ERROR") {
    return { color: "var(--err)", background: "var(--err-bg)" };
  }
  if (severity === "WARN") {
    return { color: "var(--warn)", background: "var(--warn-bg)" };
  }
  return { color: "var(--ink-soft)", background: "var(--bg-muted)" };
}

export function Workspace() {
  const [jurisdiction, setJurisdiction] = useState<Jurisdiction>("federal");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RunResponse | null>(null);

  const byName = useMemo(() => {
    const map = new Map<string, File>();
    for (const f of files) {
      map.set(f.name.toLowerCase().replace(/\s+/g, "_"), f);
    }
    return map;
  }, [files]);

  const hasExcel = files.some((f) => isExcelName(f.name));
  const missingRequired = hasExcel
    ? []
    : REQUIRED_CSV.filter((n) => !byName.has(n));

  async function onRun() {
    setError(null);
    setResult(null);
    if (!hasExcel && missingRequired.length) {
      setError(
        `Missing required files: ${missingRequired.join(", ")}. Or upload a client .xlsx workbook.`,
      );
      return;
    }
    setBusy(true);
    try {
      const body = new FormData();
      body.append("jurisdiction", jurisdiction);
      for (const f of files) {
        const name = f.name.toLowerCase().replace(/\s+/g, "_");
        body.append("files", f, name);
      }
      const res = await fetch("/api/run", { method: "POST", body });
      const data = (await res.json()) as RunResponse & { detail?: unknown };
      if (!res.ok) {
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
              ? JSON.stringify(data.detail)
              : "Request failed";
        throw new Error(detail);
      }
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section id="workspace" className="bg-[var(--bg-muted)]">
      <div className="mx-auto max-w-6xl px-6 py-12 md:px-8 md:py-16">
        <div className="mb-8 max-w-2xl">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--muted)]">
            Workspace
          </p>
          <h2 className="text-2xl font-bold tracking-[-0.03em] text-[var(--ink)] md:text-3xl">
            Drop workbook or Final-tab CSVs
          </h2>
          <p className="mt-2 text-[15px] leading-relaxed text-[var(--ink-soft)]">
            Export from your Google Sheet build as .xlsx or CSV, then upload one
            organization at a time. No app login — IRS portal passwords stay with
            you. At upload we remove exact $1.00 rows and Schedule B / ledger
            expenses under $1.00 (sign off in Deleted records). Download XML +
            recon, then upload the XML in that client&apos;s IRS Political
            Organization account only.
          </p>
        </div>

        <div className="mb-5 grid gap-3 sm:grid-cols-2">
          <div className="surface px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--muted)]">
              Sub-$1 cleanup
            </p>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">
              Exact $1.00 on A/B/ledger; expenses strictly under $1.00 on B + ledger.
            </p>
          </div>
          <div className="surface px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--muted)]">
              Per-client IRS login
            </p>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">
              One org per run. You upload XML in each client&apos;s separate IRS
              portal — credentials never stored here.
            </p>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2 lg:gap-5">
          <div className="surface p-5 md:p-6">
            <label className="mb-4 block">
              <span className="mb-1.5 block text-sm font-medium text-[var(--ink)]">
                Jurisdiction
              </span>
              <select
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value as Jurisdiction)}
                className="field"
              >
                <option value="federal">Federal (IRS 8872)</option>
                <option value="texas">Texas TEC (blocked until spec)</option>
                <option value="both">Both</option>
              </select>
            </label>

            <label className="dropzone">
              <span className="border border-[var(--line)] px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--ink)]">
                Upload files
              </span>
              <span className="text-sm font-medium text-[var(--ink)]">
                Click to select .xlsx and/or .csv files
              </span>
              <span className="text-sm text-[var(--muted)]">
                Workbook sheets used: Cover Page, Schedule A Final, Schedule B Final, PL.
                Or CSVs: {REQUIRED_CSV.join(", ")}
              </span>
              <input
                type="file"
                accept=".csv,.xlsx,.xlsm,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                multiple
                className="sr-only"
                onChange={(e) => {
                  const list = Array.from(e.target.files ?? []);
                  setFiles(list);
                  setResult(null);
                  setError(null);
                }}
              />
              {files.length > 0 && (
                <ul
                  className="mt-1 w-full space-y-1 border-t border-[var(--line)] pt-3 text-sm text-[var(--ink-soft)]"
                  style={{ fontFamily: "var(--mono)" }}
                >
                  {files.map((f) => (
                    <li key={f.name} className="truncate">
                      {f.name}
                    </li>
                  ))}
                </ul>
              )}
            </label>

            <p className="mt-3 text-xs text-[var(--muted)]">
              Optional: {OPTIONAL.join(", ")}. Reject uploads that include password /
              login columns.
            </p>

            <button
              type="button"
              onClick={onRun}
              disabled={busy || files.length === 0}
              className="btn-primary mt-6"
            >
              {busy ? "Running pipeline…" : "Build filing package"}
            </button>

            {error && (
              <p
                className="mt-4 border border-[var(--err)] px-3 py-2 text-sm leading-relaxed"
                style={{ color: "var(--err)", background: "var(--err-bg)" }}
                role="alert"
              >
                {error}
              </p>
            )}
          </div>

          <div className="surface flex min-h-[320px] flex-col p-5 md:p-6">
            {!result && !busy && (
              <div className="flex flex-1 flex-col justify-center">
                <p className="text-lg font-semibold tracking-[-0.02em] text-[var(--ink)]">
                  Results appear here
                </p>
                <p className="mt-2 max-w-sm text-sm leading-relaxed text-[var(--ink-soft)]">
                  After a successful federal run: download Form 8872 XML, check the
                  deleted-records cleanup log, then upload XML in that client&apos;s
                  IRS account.
                </p>
              </div>
            )}

            {busy && (
              <div className="flex flex-1 flex-col justify-center gap-2">
                <div className="h-px w-full bg-[var(--line-strong)]" />
                <p className="text-sm font-medium text-[var(--ink-soft)]">
                  Ingest → sub-$1 cleanup → clean → roll-up → compliance → XML → reconcile…
                </p>
              </div>
            )}

            {result && (
              <div className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <span
                      className="inline-flex border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.06em]"
                      style={{
                        color: result.ok ? "var(--ok)" : "var(--err)",
                        background: result.ok ? "var(--ok-bg)" : "var(--err-bg)",
                        borderColor: result.ok ? "var(--ok)" : "var(--err)",
                      }}
                    >
                      {result.ok ? "Ready for human review" : "Needs attention"}
                    </span>
                    <p className="mt-2 text-lg font-semibold tracking-[-0.02em] text-[var(--ink)]">
                      {result.organization_name || "Filing package"}
                    </p>
                    {result.ein && (
                      <p className="text-sm text-[var(--muted)]">EIN {result.ein}</p>
                    )}
                  </div>
                  <p
                    className="border border-[var(--line)] px-2 py-1 text-xs font-medium text-[var(--ink-soft)]"
                    style={{ fontFamily: "var(--mono)" }}
                  >
                    A {result.schedule_a_count ?? "—"} · B {result.schedule_b_count ?? "—"}
                  </p>
                </div>

                <div className="border border-[var(--line)] bg-[var(--bg-muted)] px-3 py-2.5">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                    Upload cleanup
                  </p>
                  <p className="mt-1 text-sm text-[var(--ink)]">
                    {(result.deleted_count ?? 0) === 0
                      ? "No $1.00 / sub-$1 rows removed this run."
                      : `${result.deleted_count} row(s) removed at upload${
                          result.deleted_total ? ` ($${result.deleted_total})` : ""
                        }. Review Deleted records before filing.`}
                  </p>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Next: download XML → log into this organization&apos;s IRS portal →
                    upload there.
                  </p>
                </div>

                {result.error && (
                  <p
                    className="whitespace-pre-wrap border px-3 py-2 text-sm"
                    style={{
                      color: "var(--err)",
                      background: "var(--err-bg)",
                      borderColor: "var(--err)",
                    }}
                  >
                    {result.error}
                  </p>
                )}

                <div className="flex flex-wrap gap-2">
                  {result.federal_xml_base64 && (
                    <button
                      type="button"
                      className="btn-primary !px-3 !py-1.5 text-sm"
                      onClick={() =>
                        downloadBase64(
                          result.federal_xml_base64!,
                          result.federal_xml_filename || "form_8872.xml",
                          "application/xml",
                        )
                      }
                    >
                      Download XML
                    </button>
                  )}
                  {result.reconciliation && (
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() =>
                        downloadText(result.reconciliation!, "reconciliation_report.txt")
                      }
                    >
                      Reconciliation
                    </button>
                  )}
                  {result.deleted_records && (
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() =>
                        downloadText(result.deleted_records!, "deleted_records.txt")
                      }
                    >
                      Deleted records
                    </button>
                  )}
                  {result.findings.length > 0 && (
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() =>
                        downloadText(
                          JSON.stringify({ findings: result.findings }, null, 2),
                          "findings.json",
                        )
                      }
                    >
                      Findings JSON
                    </button>
                  )}
                </div>

                <div>
                  <p className="mb-2 text-sm font-semibold text-[var(--ink)]">
                    Findings ({result.findings.length})
                  </p>
                  <ul className="max-h-56 space-y-2 overflow-auto pr-1">
                    {result.findings.length === 0 && (
                      <li className="text-sm text-[var(--muted)]">No findings.</li>
                    )}
                    {result.findings.map((f) => {
                      const tone = severityStyles(f.severity);
                      return (
                        <li
                          key={`${f.id}-${f.row ?? 0}-${f.message.slice(0, 24)}`}
                          className="border border-[var(--line)] bg-white px-3 py-2 text-sm"
                        >
                          <span
                            className="mr-2 inline-flex px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                            style={tone}
                          >
                            {f.severity}
                          </span>
                          <span className="text-[var(--ink-soft)]">{f.message}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>

                {result.reconciliation && (
                  <pre
                    className="max-h-44 overflow-auto whitespace-pre-wrap border border-[var(--line)] bg-[var(--bg-muted)] p-3 text-[11px] leading-relaxed text-[var(--ink-soft)]"
                    style={{ fontFamily: "var(--mono)" }}
                  >
                    {result.reconciliation}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>

        <footer className="mt-10 flex flex-wrap gap-x-8 gap-y-2 border-t border-[var(--line)] pt-6 text-xs text-[var(--muted)]">
          <span>Sub-$1 + $1.00 cleanup at upload</span>
          <span>Human uploads XML — separate IRS login per client</span>
          <span>Texas blocked until TEC spec</span>
        </footer>
      </div>
    </section>
  );
}
