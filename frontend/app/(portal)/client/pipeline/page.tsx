"use client";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { Skeleton } from "@/components/kit/skeleton";
import { useClientPipeline } from "@/lib/api/hooks";

const COLUMNS = ["sourced", "screened", "assessed", "submitted", "interview", "offer", "placed"];

export default function ClientPipelinePage() {
  const { data, isLoading, isError, refetch } = useClientPipeline();
  return (
    <AppShell role="client" title="Candidate pipeline">
      <p className="mb-4 text-xs text-muted">Live stage of every candidate in process for your roles (read-only).</p>
      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-7">{COLUMNS.map((c) => <Skeleton key={c} className="h-28" />)}</div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load your pipeline</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <SectionCard title="Pipeline by stage">
          <div className="grid grid-flow-col auto-cols-[minmax(170px,1fr)] gap-3 overflow-x-auto pb-2 xl:grid-flow-row xl:grid-cols-7">
            {COLUMNS.map((stage) => {
              const rows = data.stages[stage] ?? [];
              return (
                <div key={stage} className="rounded-xl border border-cardline bg-card p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted">{stage}</span>
                    <span className="text-xs text-muted">{rows.length}</span>
                  </div>
                  <div className="space-y-2">
                    {rows.length === 0 ? <p className="py-3 text-center text-xs text-muted">—</p>
                      : rows.map((r) => (
                        <div key={r.id} className="rounded-lg bg-page px-3 py-2 text-sm text-ink shadow-sm">
                          <div className="font-medium">{r.candidate}</div>
                          <div className="text-[11px] text-muted">{r.job}</div>
                        </div>
                      ))}
                  </div>
                </div>
              );
            })}
          </div>
        </SectionCard>
      )}
    </AppShell>
  );
}
