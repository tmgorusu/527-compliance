export function TesterGuide() {
  return (
    <section
      id="access"
      className="border-b border-[var(--line)] bg-[var(--bg)]"
    >
      <div className="mx-auto max-w-6xl px-6 py-10 md:px-8 md:py-12">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--muted)]">
          For testers
        </p>
        <h2 className="text-xl font-bold tracking-[-0.02em] text-[var(--ink)] md:text-2xl">
          Access &amp; what to try first
        </h2>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-[var(--ink-soft)]">
          No login is required for this tool. Open the site, upload one organization&apos;s
          workbook, download XML, then sign in to{" "}
          <strong>that client&apos;s</strong> IRS Political Organization portal yourself.
        </p>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="surface p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--muted)]">
              Link
            </p>
            <p className="mt-2 text-sm font-medium text-[var(--ink)] break-all">
              https://527-compliance.vercel.app
            </p>
            <p className="mt-2 text-xs text-[var(--muted)]">
              Access: open URL — no app password. IRS portal passwords stay with you.
            </p>
          </div>
          <div className="surface p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--muted)]">
              Try first
            </p>
            <ol className="mt-2 list-decimal space-y-1.5 pl-4 text-sm text-[var(--ink-soft)]">
              <li>Upload one client .xlsx (or Sheet export)</li>
              <li>Confirm sub-$1 / $1.00 cleanup in Deleted records</li>
              <li>Download XML + recon; review findings</li>
              <li>Upload XML in that client&apos;s IRS account only</li>
            </ol>
          </div>
          <div className="surface p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--muted)]">
              Designed around
            </p>
            <ul className="mt-2 space-y-1.5 text-sm text-[var(--ink-soft)]">
              <li>Sub-$1 expense cleanup at upload (plus exact $1.00)</li>
              <li>Separate IRS login per client — never stored here</li>
              <li>Google Sheet / Excel → filing-ready 8872 XML</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
