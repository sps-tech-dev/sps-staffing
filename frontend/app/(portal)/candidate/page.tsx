"use client";
import { AppShell } from "@/components/shell/app-shell";
import { KpiGrid } from "@/components/widgets/kpi-grid";
import { SectionCard } from "@/components/kit/section-card";
import { StatusPill } from "@/components/kit/status-pill";
import { ProgressRing } from "@/components/kit/progress-ring";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useCandidateOverview } from "@/lib/api/hooks";
import { Briefcase, CalendarCheck, Award } from "lucide-react";

export default function CandidateDashboard() {
  const { data, isLoading, isError, refetch } = useCandidateOverview();

  return (
    <AppShell role="candidate" title="Candidate Dashboard">
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load your dashboard</p>
          <p className="max-w-xs text-sm text-muted">Your session may have expired. Please sign in again or retry.</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">
            Retry
          </button>
        </div>
      ) : (
        <>
          <KpiGrid items={[
            { value: data.applications, label: "Applications", icon: <Briefcase size={20} />, accent: "#1B5FE8" },
            { value: data.interviews, label: "Interviews", icon: <CalendarCheck size={20} />, accent: "#5B8FFF" },
            { value: data.offers, label: "Offers", icon: <Award size={20} />, accent: "#16A34A" },
            { value: `${data.profileComplete}%`, label: "Profile complete", icon: <Award size={20} />, accent: "#E8A020" },
          ]} />
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <SectionCard title="Recent applications">
                {data.recent.length === 0 ? (
                  <EmptyState
                    icon={<Briefcase size={28} />}
                    title="No applications yet"
                    hint="Applications placed by our recruiting team appear here with live stages."
                  />
                ) : (
                  <div className="divide-y divide-cardline">
                    {data.recent.map((r) => (
                      <div key={r.id} className="flex items-center justify-between py-3">
                        <span className="text-sm text-ink">{r.job}</span>
                        <StatusPill status={r.stage} />
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            </div>
            <SectionCard title="Profile strength">
              <div className="flex items-center justify-center py-4">
                <ProgressRing value={data.profileComplete} size={120} stroke={12} />
              </div>
            </SectionCard>
          </div>
        </>
      )}
    </AppShell>
  );
}
