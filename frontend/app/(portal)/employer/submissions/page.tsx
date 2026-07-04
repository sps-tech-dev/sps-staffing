"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useSubmissions, useUpdateSubmission } from "@/lib/api/hooks";
import { Send } from "lucide-react";

const STATUSES = ["submitted", "under_review", "shortlisted", "rejected"];
const STATUS_STYLE: Record<string, string> = {
  submitted: "bg-[#EFF6FF] text-[#1B5FE8]",
  under_review: "bg-[#FFFBEB] text-[#E8A020]",
  shortlisted: "bg-[#F0FDF4] text-[#16A34A]",
  rejected: "bg-[#FEF2F2] text-[#DC2626]",
};

export default function SubmissionsPage() {
  const { data, isLoading, isError, refetch } = useSubmissions();
  const update = useUpdateSubmission();
  const [draft, setDraft] = useState<Record<string, string>>({});

  return (
    <AppShell role="employee" title="Submissions">
      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load submissions</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <SectionCard title="Candidates submitted to clients">
          {data.length === 0 ? (
            <EmptyState icon={<Send size={28} />} title="No submissions yet" hint="Submit a candidate to a client from the pipeline board." />
          ) : (
            <div className="divide-y divide-cardline">
              {data.map((s) => (
                <div key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ink">{s.candidate ?? "—"}</div>
                    <div className="text-xs text-muted">{s.job ?? "—"}</div>
                    {s.client_feedback && <div className="mt-1 text-xs text-ink/70">“{s.client_feedback}”</div>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${STATUS_STYLE[s.status] ?? "bg-page text-muted"}`}>
                      {s.status.replace("_", " ")}
                    </span>
                    <select
                      value=""
                      onChange={(e) => e.target.value && update.mutate({ id: s.id, status: e.target.value })}
                      className="rounded-lg border border-cardline bg-white px-2 py-1 text-xs text-ink outline-none focus:border-[#1B5FE8]"
                      aria-label="Set status"
                    >
                      <option value="">Set status…</option>
                      {STATUSES.map((st) => <option key={st} value={st}>{st.replace("_", " ")}</option>)}
                    </select>
                    <input
                      placeholder="Client feedback…"
                      defaultValue={s.client_feedback ?? ""}
                      onChange={(e) => setDraft((d) => ({ ...d, [s.id]: e.target.value }))}
                      onBlur={() => draft[s.id] !== undefined && update.mutate({ id: s.id, client_feedback: draft[s.id] })}
                      className="w-40 rounded-lg border border-cardline bg-white px-2 py-1 text-xs text-ink outline-none focus:border-[#1B5FE8]"
                    />
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
