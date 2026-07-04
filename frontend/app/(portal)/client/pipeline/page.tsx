"use client";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { Skeleton } from "@/components/kit/skeleton";
import { useClientPipeline } from "@/lib/api/hooks";

// F4: the client view groups the 21-stage B.5 vocabulary into the steps a
// hiring manager thinks in. Read-only on purpose — stage changes are a staff
// action; the client acts through Submissions (feedback) and Offers (HR).
const GROUPS: { label: string; stages: string[] }[] = [
  { label: "Screening", stages: ["applied", "screening"] },
  { label: "Assessment", stages: ["aptitude_test", "aptitude_passed", "aptitude_failed"] },
  { label: "Internal", stages: ["internal_interview", "internal_passed", "rtr_pending"] },
  { label: "Submitted", stages: ["submitted_to_client"] },
  { label: "Your Rounds", stages: ["client_round_1", "client_round_2", "client_round_3"] },
  { label: "Offer", stages: ["offer", "offer_accepted"] },
  { label: "Joined", stages: ["joined", "guarantee", "invoiced", "paid"] },
];

export default function ClientPipelinePage() {
  const { data, isLoading, isError, refetch } = useClientPipeline();
  return (
    <AppShell role="client" title="Candidate pipeline">
      <p className="mb-4 text-xs text-muted">Live stage of every candidate in process for your roles (read-only).</p>
      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-7">{GROUPS.map((g) => <Skeleton key={g.label} className="h-28" />)}</div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load your pipeline</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <SectionCard title="Pipeline by stage">
          <div className="grid grid-flow-col auto-cols-[minmax(170px,1fr)] gap-3 overflow-x-auto pb-2 xl:grid-flow-row xl:grid-cols-7">
            {GROUPS.map((g) => {
              const rows = g.stages.flatMap((s) => data.stages[s] ?? []);
              return (
                <div key={g.label} className="rounded-xl border border-cardline bg-card p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted">{g.label}</span>
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
