"use client";
import { AppShell } from "@/components/shell/app-shell";
import { KpiGrid } from "@/components/widgets/kpi-grid";
import { SectionCard } from "@/components/kit/section-card";
import { StatusPill } from "@/components/kit/status-pill";
import { PipelineDonut } from "@/components/kit/pipeline-donut";
import { useEmployerOverview } from "@/lib/api/hooks";
import { Briefcase, Users, CalendarCheck, CheckCircle2 } from "lucide-react";

export default function EmployerDashboard() {
  const { data } = useEmployerOverview();
  return (
    <AppShell role="client" title="Employer Dashboard">
      <KpiGrid items={[
        { value: data?.openJobs ?? "—", label: "Open jobs", icon: <Briefcase size={20}/>, accent:"#1B5FE8" },
        { value: data?.inPipeline ?? "—", label: "In pipeline", icon: <Users size={20}/>, accent:"#5B8FFF" },
        { value: data?.interviews ?? "—", label: "Interviews", icon: <CalendarCheck size={20}/>, accent:"#E8A020" },
        { value: data?.placements ?? "—", label: "Placements", icon: <CheckCircle2 size={20}/>, accent:"#16A34A" },
      ]}/>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <SectionCard title="Pipeline funnel">
          <PipelineDonut segments={data?.funnel ?? []} />
        </SectionCard>
        <div className="lg:col-span-2">
          <SectionCard title="Active pipeline">
            <div className="divide-y divide-cardline">
              {data?.pipeline.map((p) => (
                <div key={p.id} className="flex items-center justify-between py-3">
                  <div><span className="text-sm font-medium text-ink">{p.candidate}</span>
                    <span className="ml-2 text-xs text-muted">{p.job}</span></div>
                  <StatusPill status={p.stage} />
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </AppShell>
  );
}
