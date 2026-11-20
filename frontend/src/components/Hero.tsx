import Link from "next/link";

export function Hero() {
  return (
    <section className="relative isolate border-b border-[var(--line)]">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 md:px-8">
        <Link href="/" className="animate-fade-up text-[14px] font-semibold tracking-[-0.02em] text-[var(--ink)]">
          527 Filing
        </Link>
        <nav className="flex items-center gap-5 animate-fade-up">
          <a
            href="#workspace"
            className="hidden text-sm font-medium text-[var(--ink-soft)] transition-colors hover:text-[var(--ink)] sm:inline"
          >
            Workspace
          </a>
          <a href="#workspace" className="btn-primary !px-3.5 !py-1.5 text-sm">
            Start filing
          </a>
        </nav>
      </header>

      <div className="mx-auto grid max-w-6xl items-start gap-8 px-6 pb-10 pt-6 md:grid-cols-[1.15fr_0.85fr] md:gap-10 md:px-8 md:pb-12 md:pt-8">
        <div>
          <p className="animate-fade-up mb-3 text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--muted)]">
            Federal Form 8872 · Texas coming soon
          </p>
          <h1 className="animate-fade-up-d1 max-w-lg text-[clamp(1.75rem,3.5vw,2.35rem)] font-bold leading-[1.12] tracking-[-0.03em] text-[var(--ink)]">
            Financial infrastructure for 527 filings
          </h1>
          <p className="animate-fade-up-d2 mt-3 max-w-md text-[15px] leading-relaxed text-[var(--ink-soft)]">
            Turn a client workbook or Schedule A/B CSV exports into filing-ready IRS XML.
            Review findings, reconcile to the P&amp;L, then download — a human uploads to
            the portal.
          </p>
          <div className="animate-fade-up-d2 mt-5 flex flex-wrap items-center gap-2.5">
            <a href="#workspace" className="btn-primary !px-4 !py-2 text-sm">
              Open workspace
            </a>
            <a href="#workspace" className="btn-secondary !px-4 !py-2 text-sm">
              Upload workbook
            </a>
          </div>
          <p className="animate-fade-up-d2 mt-3 text-xs text-[var(--muted)]">
            No portal passwords. Output files only.
          </p>
        </div>

        <div className="animate-fade-up-d2 hidden sm:block">
          <div className="surface p-4">
            <div className="mb-3 flex items-center justify-between border-b border-[var(--line)] pb-3">
              <div>
                <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-[var(--muted)]">
                  Pipeline
                </p>
                <p className="mt-0.5 text-sm font-semibold text-[var(--ink)]">
                  Form 8872 build
                </p>
              </div>
              <span className="border border-[var(--line)] px-2 py-0.5 text-[11px] font-semibold text-[var(--ok)]">
                Ready
              </span>
            </div>
            <ol className="space-y-0">
              {[
                "Ingest & clean CSVs",
                "$1 deletion + thresholds",
                "Roll-ups & compliance",
                "XSD-valid XML + recon",
              ].map((step, i) => (
                <li
                  key={step}
                  className="flex items-center gap-3 border-b border-[var(--line)] py-2.5 last:border-b-0"
                >
                  <span
                    className="w-5 text-[11px] font-semibold text-[var(--muted)]"
                    style={{ fontFamily: "var(--mono)" }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="text-sm font-medium text-[var(--ink)]">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
