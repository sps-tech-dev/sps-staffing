"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { useIssueTest, useTests } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import type { IssueResult, TestRow } from "@/lib/api/types";
import { GraduationCap, ShieldCheck, Copy, AlertTriangle } from "lucide-react";

function TestsTable({ rows, waiveControl }: {
  rows: TestRow[]; waiveControl?: (t: TestRow) => React.ReactNode;
}) {
  if (rows.length === 0) {
    return <EmptyState icon={<GraduationCap size={28} />} title="No tests yet"
      hint="Issued aptitude tests appear here with status and results." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-cardline text-xs uppercase tracking-wide text-muted">
            <th className="py-2 pr-3">Application</th><th className="py-2 pr-3">Attempt</th>
            <th className="py-2 pr-3">Status</th><th className="py-2 pr-3">Result</th>
            <th className="py-2 pr-3">Submitted</th>{waiveControl && <th className="py-2">Waiver</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-cardline">
          {rows.map((t) => (
            <tr key={t.id}>
              <td className="py-2 pr-3 font-mono text-xs text-muted">{t.application_id.slice(0, 8)}…</td>
              <td className="py-2 pr-3 text-muted">#{t.attempt_no}</td>
              <td className="py-2 pr-3"><StatusPill status={t.status} /></td>
              <td className="py-2 pr-3">
                {t.waived ? (
                  // B.7 honesty: a waiver is VISIBLY distinct and NEVER shows a numeric score
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#FFFBEB] px-2 py-0.5 text-[11px] font-semibold text-[#D97706]">
                    <ShieldCheck size={11} /> Waived by admin — no score
                  </span>
                ) : t.score != null ? (
                  <span className={t.passed ? "font-semibold text-[#16A34A]" : "font-semibold text-[#DC2626]"}>
                    {(t.score * 100).toFixed(0)}% · {t.passed ? "Passed" : "Failed"}
                  </span>
                ) : (
                  <span className="text-muted">—</span>
                )}
              </td>
              <td className="py-2 pr-3 text-xs text-muted">
                {t.submitted_at ? new Date(t.submitted_at).toLocaleString() : "—"}
              </td>
              {waiveControl && <td className="py-2">{waiveControl(t)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One-time link modal: the raw token appears EXACTLY once (the backend stores
 *  only its hash) — copy it now or reissue. */
function IssueLinkModal({ issued, onClose }: { issued: IssueResult; onClose: () => void }) {
  const takeUrl = `${window.location.origin}${issued.take_path.replace(/^\/api/, "")}`;
  const [copied, setCopied] = useState(false);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-cardline bg-card p-5 shadow-lg">
        <h3 className="font-display text-base font-bold text-ink">Test issued — one-time link</h3>
        <p className="mt-1 inline-flex items-center gap-1 text-xs text-[#D97706]">
          <AlertTriangle size={12} /> This link is shown ONCE. Copy and send it to the candidate now.
        </p>
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-cardline bg-page px-3 py-2">
          <code className="min-w-0 flex-1 truncate text-xs text-ink">{takeUrl}</code>
          <button onClick={() => { navigator.clipboard.writeText(takeUrl); setCopied(true); }}
            className="inline-flex items-center gap-1 rounded-lg bg-sps-blue px-2.5 py-1 text-xs font-semibold text-white">
            <Copy size={12} /> {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="mt-2 text-xs text-muted">
          {issued.question_count} questions · {issued.time_limit_minutes} min · valid until{" "}
          {new Date(issued.valid_until).toLocaleString()} · attempt #{issued.attempt_no}
        </p>
        <div className="mt-4 flex justify-end">
          <button onClick={onClose} className="rounded-lg bg-page px-3 py-1.5 text-sm text-ink hover:bg-cardline">Done</button>
        </div>
      </div>
    </div>
  );
}

export default function AssessmentsPage() {
  const { data, isLoading, isError, refetch } = useTests();
  const issue = useIssueTest();
  const [appId, setAppId] = useState("");
  const [issued, setIssued] = useState<IssueResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  function onIssue(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    issue.mutate(appId.trim(), {
      onSuccess: (r) => { setIssued(r); setAppId(""); },
      onError: (e) => setErr(e instanceof ApiError
        ? (e.code === "STAGE_INVALID" || e.code === "ILLEGAL_TRANSITION"
            ? "The application must be at the Aptitude Test stage to issue a test."
            : e.message)
        : "Couldn't issue the test — please retry."),
    });
  }

  return (
    <AppShell role="employee" title="Assessments">
      <SectionCard title="Issue an aptitude test">
        <p className="mb-3 text-xs text-muted">
          The application must be at the <strong>Aptitude Test</strong> stage (the server enforces it).
          The candidate link is one-time and expires automatically.
        </p>
        <form onSubmit={onIssue} className="flex flex-wrap items-end gap-2" noValidate>
          <label className="text-xs text-muted">Application ID
            <input value={appId} onChange={(e) => setAppId(e.target.value)}
              placeholder="paste the application id from the pipeline"
              className="mt-1 block w-80 rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
          </label>
          <button type="submit" disabled={!appId.trim() || issue.isPending}
            className="rounded-lg bg-sps-blue px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {issue.isPending ? "Issuing…" : "Issue test"}
          </button>
        </form>
        {err && <p role="alert" className="mt-3 rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">{err}</p>}
      </SectionCard>

      <div className="mt-6">
        <SectionCard title="Tests">
          {isLoading ? <Skeleton className="h-32" />
            : isError || !data ? (
              <p className="text-sm text-muted">Couldn&apos;t load tests.{" "}
                <button onClick={() => refetch()} className="text-[#1B5FE8] underline">Retry</button></p>
            ) : <TestsTable rows={data} />}
        </SectionCard>
      </div>

      {issued && <IssueLinkModal issued={issued} onClose={() => setIssued(null)} />}
    </AppShell>
  );
}
