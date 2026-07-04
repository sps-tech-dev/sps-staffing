"use client";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { KpiGrid } from "@/components/widgets/kpi-grid";
import { useEmployeeOverview } from "@/lib/api/hooks";
import type { QueueItem } from "@/lib/api/types";
import { ClipboardList, AlertTriangle, Flame, Timer } from "lucide-react";

function SlaQueue({ queue }: { queue: QueueItem[] }) {
  if (queue.length === 0) {
    return <EmptyState icon={<Timer size={28} />} title="Queue is clear"
      hint="Active applications appear here with their SLA age." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-cardline text-xs uppercase tracking-wide text-muted">
            <th className="py-2 pr-3">Candidate</th><th className="py-2 pr-3">Job</th>
            <th className="py-2 pr-3">Stage</th><th className="py-2 pr-3">Age (h)</th>
            <th className="py-2">SLA</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-cardline">
          {queue.map((q) => (
            <tr key={q.id}>
              <td className="py-2 pr-3 font-medium text-ink">{q.candidate}</td>
              <td className="py-2 pr-3 text-muted">{q.job}</td>
              <td className="py-2 pr-3"><StatusPill status={q.stage} /></td>
              <td className="py-2 pr-3 text-muted">{q.ageHours}</td>
              <td className="py-2">
                <span className={
                  q.sla === "breached" ? "rounded-full bg-[#FEF2F2] px-2 py-0.5 text-[11px] font-semibold text-[#DC2626]"
                  : q.sla === "warning" ? "rounded-full bg-[#FFFBEB] px-2 py-0.5 text-[11px] font-semibold text-[#D97706]"
                  : "rounded-full bg-[#F0FDF4] px-2 py-0.5 text-[11px] font-semibold text-[#16A34A]"
                }>{q.sla}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Page() {
  const { data, isLoading, isError, refetch } = useEmployeeOverview();
  return (
    <AppShell role="employee" title="SLA Board">
      <p className="mb-4 text-xs text-muted">Stage-ageing SLAs across active applications. Amber is approaching target; red has breached.</p>
      {isLoading ? <Skeleton className="h-40" />
        : isError || !data ? (
          <p className="text-sm text-muted">Couldn&apos;t load the board.{" "}
            <button onClick={() => refetch()} className="text-[#1B5FE8] underline">Retry</button></p>
        ) : (
          <>
            <KpiGrid items={[
              { value: data.open, label: "Active applications", icon: <ClipboardList size={20} />, accent: "#1B5FE8" },
              { value: data.breaching, label: "Approaching SLA", icon: <AlertTriangle size={20} />, accent: "#D97706" },
              { value: data.breached, label: "SLA breached", icon: <Flame size={20} />, accent: "#DC2626" },
            ]} />
            <div className="mt-6">
              <SectionCard title="Queue (oldest first)">
                <SlaQueue queue={data.queue} />
              </SectionCard>
            </div>
          </>
        )}
    </AppShell>
  );
}
