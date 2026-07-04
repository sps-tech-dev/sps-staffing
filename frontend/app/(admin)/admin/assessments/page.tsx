"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { useFeatures, useTests, useWaiveTest } from "@/lib/api/hooks";
import type { TestRow } from "@/lib/api/types";
import { GraduationCap, ShieldCheck } from "lucide-react";

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

/** Waiver reason modal — reason is REQUIRED (the server 422s without one). */
function WaiveModal({ t, onCancel, onDone }: { t: TestRow; onCancel: () => void; onDone: () => void }) {
  const waive = useWaiveTest();
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<"pass" | "fail">("pass");
  const [err, setErr] = useState<string | null>(null);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-sm rounded-2xl border border-cardline bg-card p-5 shadow-lg">
        <h3 className="font-display text-base font-bold text-ink">Waive this test — reason required</h3>
        <p className="mt-1 text-xs text-muted">
          A waiver advances the candidate WITHOUT a score (never fabricates one) and is audited.
        </p>
        <div className="mt-3 flex gap-2">
          {(["pass", "fail"] as const).map((r) => (
            <label key={r} className={`flex-1 cursor-pointer rounded-lg border px-3 py-2 text-center text-sm capitalize ${result === r ? "border-[#1B5FE8] bg-[#EFF6FF] text-ink" : "border-cardline text-muted"}`}>
              <input type="radio" className="sr-only" checked={result === r} onChange={() => setResult(r)} />
              waive as {r}
            </label>
          ))}
        </div>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} autoFocus
          placeholder="e.g. senior lateral hire — client waived aptitude round"
          className="mt-3 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
        {err && <p role="alert" className="mt-2 text-xs text-[#DC2626]">{err}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-page">Cancel</button>
          <button disabled={!reason.trim() || waive.isPending}
            onClick={() => waive.mutate({ appId: t.application_id, testId: t.id, result, reason: reason.trim() },
              { onSuccess: onDone, onError: (e) => setErr((e as Error).message ?? "Couldn't waive.") })}
            className="rounded-lg bg-[#D97706] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">
            Confirm waiver
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminAssessmentsPage() {
  const { data, isLoading, isError, refetch } = useTests();
  const features = useFeatures();
  const waiverOn = features.data?.features?.assessment_waiver === true;
  const [waiving, setWaiving] = useState<TestRow | null>(null);

  // The waiver control renders ONLY when the flag is on (the endpoint 404s when
  // off — we never show a button that 404s) AND only on rows the server would
  // accept (not graded, not already waived).
  const waiveControl = waiverOn
    ? (t: TestRow) =>
        t.waived || t.submitted_at ? <span className="text-xs text-muted">—</span> : (
          <button onClick={() => setWaiving(t)}
            className="rounded-lg border border-[#D97706]/40 px-2.5 py-1 text-xs font-semibold text-[#D97706] hover:bg-[#FFFBEB]">
            Waive…
          </button>
        )
    : undefined;

  return (
    <AppShell role="admin" title="Assessments">
      {!waiverOn && !features.isLoading && (
        <p className="mb-4 rounded-lg bg-page px-3 py-2 text-xs text-muted">
          The admin waiver capability is disabled for this environment (feature flag off) — tests are tracked read-only here.
        </p>
      )}
      <SectionCard title="All tests">
        {isLoading ? <Skeleton className="h-32" />
          : isError || !data ? (
            <p className="text-sm text-muted">Couldn&apos;t load tests.{" "}
              <button onClick={() => refetch()} className="text-[#1B5FE8] underline">Retry</button></p>
          ) : <TestsTable rows={data} waiveControl={waiveControl} />}
      </SectionCard>
      {waiving && <WaiveModal t={waiving} onCancel={() => setWaiving(null)} onDone={() => setWaiving(null)} />}
    </AppShell>
  );
}
