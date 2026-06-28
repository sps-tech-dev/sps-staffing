"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { useClientSubmissions, useClientSubmissionFeedback } from "@/lib/api/hooks";
import { Users, Check, X } from "lucide-react";

const SUB_STYLE: Record<string, string> = {
  submitted: "bg-[#EFF6FF] text-[#1B5FE8]", under_review: "bg-[#FFFBEB] text-[#E8A020]",
  shortlisted: "bg-[#F0FDF4] text-[#16A34A]", rejected: "bg-[#FEF2F2] text-[#DC2626]",
};

export default function ClientSubmissionsPage() {
  const { data, isLoading, isError, refetch } = useClientSubmissions();
  const feedback = useClientSubmissionFeedback();
  const [note, setNote] = useState<Record<string, string>>({});

  return (
    <AppShell role="client" title="Submitted candidates">
      <p className="mb-4 text-xs text-muted">Candidates our recruiters submitted for your roles. Approve to shortlist, or reject.</p>
      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load submissions</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <SectionCard title="Candidates submitted to you">
          {data.length === 0 ? (
            <EmptyState icon={<Users size={28} />} title="No candidates yet" hint="Submitted candidates for your roles will appear here." />
          ) : (
            <div className="divide-y divide-cardline">
              {data.map((s) => (
                <div key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ink">{s.candidate ?? "—"}</div>
                    <div className="flex items-center gap-2 text-xs text-muted">{s.job ?? "—"} {s.stage && <StatusPill status={s.stage} />}</div>
                    {s.client_feedback && <div className="mt-1 text-xs text-ink/70">“{s.client_feedback}”</div>}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${SUB_STYLE[s.status] ?? "bg-page text-muted"}`}>{s.status.replace("_", " ")}</span>
                    <input placeholder="Note (optional)" value={note[s.id] ?? ""} onChange={(e) => setNote((m) => ({ ...m, [s.id]: e.target.value }))}
                      className="w-40 rounded-lg border border-cardline bg-white px-2 py-1 text-xs text-ink outline-none focus:border-[#1B5FE8]" />
                    <button onClick={() => feedback.mutate({ id: s.id, decision: "approve", note: note[s.id] })} disabled={feedback.isPending}
                      className="inline-flex items-center gap-1 rounded-lg bg-[#16A34A] px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-60"><Check size={12} /> Approve</button>
                    <button onClick={() => feedback.mutate({ id: s.id, decision: "reject", note: note[s.id] })} disabled={feedback.isPending}
                      className="inline-flex items-center gap-1 rounded-lg border border-[#DC2626]/40 px-2.5 py-1 text-xs font-semibold text-[#DC2626]"><X size={12} /> Reject</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      )}
    </AppShell>
  );
}
