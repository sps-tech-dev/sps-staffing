"use client";
import { AppShell } from "@/components/shell/app-shell";
import { KpiGrid } from "@/components/widgets/kpi-grid";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useClientOverview, useClientInterviews, useClientOffers } from "@/lib/api/hooks";
import { Briefcase, Users, CalendarClock, FileSignature } from "lucide-react";

export default function ClientOverviewPage() {
  const ov = useClientOverview();
  const interviews = useClientInterviews();
  const offers = useClientOffers();

  return (
    <AppShell role="client" title="Your hiring overview">
      <p className="mb-4 text-xs text-muted">Showing only your company&apos;s jobs, candidates and pipeline.</p>
      {ov.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
      ) : ov.isError || !ov.data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load your overview</p>
          <button onClick={() => ov.refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <>
          <KpiGrid items={[
            { value: ov.data.open_jobs, label: "Open jobs", icon: <Briefcase size={20} />, accent: "#1B5FE8" },
            { value: ov.data.in_pipeline, label: "In pipeline", icon: <Users size={20} />, accent: "#7C3AED" },
            { value: ov.data.interviews, label: "Interviews scheduled", icon: <CalendarClock size={20} />, accent: "#E8A020" },
            { value: ov.data.offers, label: "Offers", icon: <FileSignature size={20} />, accent: "#16A34A" },
          ]} />
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <SectionCard title="Pipeline funnel">
              <div className="space-y-2">
                {ov.data.funnel.filter((f) => f.value > 0).length === 0 ? (
                  <p className="text-sm text-muted">No candidates in the pipeline yet.</p>
                ) : ov.data.funnel.map((f) => (
                  <div key={f.label} className="flex items-center gap-2">
                    <span className="w-24 text-xs capitalize text-muted">{f.label.replace("_", " ")}</span>
                    <div className="h-2 flex-1 rounded-full bg-page">
                      <div className="h-2 rounded-full bg-[#1B5FE8]" style={{ width: `${Math.min(100, f.value * 20)}%` }} />
                    </div>
                    <span className="w-6 text-right text-xs text-ink">{f.value}</span>
                  </div>
                ))}
              </div>
            </SectionCard>
            <SectionCard title="Upcoming interviews">
              {interviews.isLoading ? <Skeleton className="h-16" />
                : !interviews.data || interviews.data.length === 0
                ? <EmptyState icon={<CalendarClock size={26} />} title="No interviews scheduled" hint="Scheduled interviews for your candidates appear here." />
                : (
                  <div className="divide-y divide-cardline">
                    {interviews.data.slice(0, 6).map((iv) => (
                      <div key={iv.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                        <span className="text-ink">{iv.candidate ?? "—"}</span>
                        <span className="text-xs text-muted">{iv.scheduled_at ? new Date(iv.scheduled_at).toLocaleString() : "TBD"} · {iv.mode} · {iv.status}</span>
                      </div>
                    ))}
                  </div>
                )}
            </SectionCard>
          </div>
          <div className="mt-6">
            <SectionCard title="Offers">
              {offers.isLoading ? <Skeleton className="h-12" />
                : !offers.data || offers.data.length === 0
                ? <EmptyState icon={<FileSignature size={26} />} title="No offers yet" hint="Offer status for your candidates appears here." />
                : (
                  <div className="divide-y divide-cardline">
                    {offers.data.map((o) => (
                      <div key={o.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                        <span className="text-ink">{o.candidate ?? "—"}</span>
                        <span className="text-xs text-muted">{o.ctc ? `₹${o.ctc.toLocaleString("en-IN")}` : "—"}{o.joining_date ? ` · joins ${o.joining_date}` : ""} · {o.status}</span>
                      </div>
                    ))}
                  </div>
                )}
            </SectionCard>
          </div>
        </>
      )}
    </AppShell>
  );
}
