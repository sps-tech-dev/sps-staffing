"use client";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useInterviews, useUpdateInterview } from "@/lib/api/hooks";
import { CalendarClock } from "lucide-react";

const MODES = ["phone", "video", "onsite"];
const STATUSES = ["scheduled", "completed", "cancelled", "no_show"];
const STATUS_STYLE: Record<string, string> = {
  scheduled: "bg-[#EFF6FF] text-[#1B5FE8]",
  completed: "bg-[#F0FDF4] text-[#16A34A]",
  cancelled: "bg-[#FEF2F2] text-[#DC2626]",
  no_show: "bg-[#FFFBEB] text-[#E8A020]",
};

// datetime-local needs "YYYY-MM-DDTHH:mm"
const toLocal = (iso: string | null) => (iso ? iso.slice(0, 16) : "");

export default function InterviewsPage() {
  const { data, isLoading, isError, refetch } = useInterviews();
  const update = useUpdateInterview();

  return (
    <AppShell role="employee" title="Interviews">
      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load interviews</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <SectionCard title="Interviews (soonest first)">
          {data.length === 0 ? (
            <EmptyState icon={<CalendarClock size={28} />} title="No interviews yet" hint="Schedule one from the pipeline board, then set the time here." />
          ) : (
            <div className="divide-y divide-cardline">
              {data.map((iv) => (
                <div key={iv.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ink">{iv.candidate ?? "—"}</div>
                    <div className="text-xs text-muted">{iv.job ?? "—"}{iv.interviewer_name ? ` · ${iv.interviewer_name}` : ""}</div>
                    {iv.feedback && <div className="mt-1 text-xs text-ink/70">“{iv.feedback}”</div>}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <input type="datetime-local" defaultValue={toLocal(iv.scheduled_at)}
                      onChange={(e) => e.target.value && update.mutate({ id: iv.id, scheduled_at: new Date(e.target.value).toISOString() })}
                      className="rounded-lg border border-cardline bg-white px-2 py-1 text-xs text-ink outline-none focus:border-[#1B5FE8]" />
                    <select value={iv.mode} onChange={(e) => update.mutate({ id: iv.id, mode: e.target.value })}
                      className="rounded-lg border border-cardline bg-white px-2 py-1 text-xs text-ink outline-none focus:border-[#1B5FE8]" aria-label="Mode">
                      {MODES.map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${STATUS_STYLE[iv.status]}`}>{iv.status.replace("_", " ")}</span>
                    <select value="" onChange={(e) => e.target.value && update.mutate({ id: iv.id, status: e.target.value })}
                      className="rounded-lg border border-cardline bg-white px-2 py-1 text-xs text-ink outline-none focus:border-[#1B5FE8]" aria-label="Set status">
                      <option value="">Status…</option>
                      {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                    </select>
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
