"use client";
import { AppShell } from "@/components/shell/app-shell";
import { KpiGrid } from "@/components/widgets/kpi-grid";
import { SectionCard } from "@/components/kit/section-card";
import { StatusPill } from "@/components/kit/status-pill";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useEmployeeOverview } from "@/lib/api/hooks";
import { ClipboardList, Timer, AlertTriangle } from "lucide-react";

const SLA_STYLE: Record<string, string> = {
  ok: "bg-[#F0FDF4] text-[#16A34A]",
  warning: "bg-[#FFFBEB] text-[#E8A020]",
  breached: "bg-[#FEF2F2] text-[#DC2626]",
};

export default function EmployeeHub() {
  const { data, isLoading, isError, refetch } = useEmployeeOverview();

  return (
    <AppShell role="employee" title="Recruiter Hub">
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load your queue</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <>
          <KpiGrid items={[
            { value: data.open, label: "Open requisitions", icon: <ClipboardList size={20} />, accent: "#1B5FE8" },
            { value: data.breaching, label: "SLA at risk", icon: <Timer size={20} />, accent: "#E8A020" },
            { value: data.breached, label: "SLA breached", icon: <AlertTriangle size={20} />, accent: "#DC2626" },
          ]} />
          <div className="mt-6">
            <SectionCard title="Requisition queue (oldest first)">
              {data.queue.length === 0 ? (
                <EmptyState icon={<ClipboardList size={28} />} title="Queue is clear" hint="No active applications need attention." />
              ) : (
                <div className="divide-y divide-cardline">
                  {data.queue.map((q) => (
                    <div key={q.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                      <div className="min-w-0">
                        <span className="text-sm font-medium text-ink">{q.candidate}</span>
                        <span className="ml-2 text-xs text-muted">{q.job}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusPill status={q.stage} />
                        <span className="text-xs text-muted">{q.ageHours}h</span>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${SLA_STYLE[q.sla]}`}>
                          {q.sla === "ok" ? "On track" : q.sla === "warning" ? "At risk" : "Breached"}
                        </span>
                      </div>
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
