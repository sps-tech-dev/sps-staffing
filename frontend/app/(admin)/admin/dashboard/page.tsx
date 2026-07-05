"use client";

import Link from "next/link";
import { Users, Building2, Briefcase, ArrowRight } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { KpiGrid } from "@/components/widgets/kpi-grid";
import { Skeleton } from "@/components/kit/skeleton";
import { FounderKpiStrip } from "@/components/widgets/founder-kpi-strip";
import { FounderCharts } from "@/components/widgets/founder-charts";
import { useAdminCandidates, useAdminClients, useAdminJobs } from "@/lib/api/hooks";

/** F1: the admin console landing — real headline totals from the admin list
 *  endpoints, plus the founder KPI strip which renders ONLY for owner/super_admin
 *  sessions (a plain admin's 403 hides it without breaking the page). */
export default function AdminDashboard() {
  const candidates = useAdminCandidates(0);
  const clients = useAdminClients(0);
  const jobs = useAdminJobs(0);
  const loading = candidates.isLoading || clients.isLoading || jobs.isLoading;

  return (
    <AppShell role="admin" title="Admin Dashboard">
      <FounderKpiStrip />
      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}
        </div>
      ) : (
        <KpiGrid items={[
          { value: candidates.data?.total ?? "—", label: "Candidates", icon: <Users size={20} />, accent: "#1B5FE8" },
          { value: clients.data?.total ?? "—", label: "Clients", icon: <Building2 size={20} />, accent: "#7C3AED" },
          { value: jobs.data?.total ?? "—", label: "Jobs", icon: <Briefcase size={20} />, accent: "#E8A020" },
        ]} />
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <SectionCard title="Manage">
          <ul className="divide-y divide-cardline text-sm">
            {[
              { href: "/admin/candidates", label: "Candidates — search, timeline, privacy" },
              { href: "/admin/clients", label: "Clients — accounts and fee overrides" },
              { href: "/admin/client-registrations", label: "Client sign-ups — approve or reject" },
              { href: "/admin/jobs", label: "Jobs — requisitions across clients" },
              { href: "/admin/audit-logs", label: "Audit logs — every privileged action" },
            ].map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="group flex items-center justify-between py-2.5 text-ink hover:text-sps-blue">
                  {l.label}
                  <ArrowRight size={15} className="text-muted group-hover:text-sps-blue" />
                </Link>
              </li>
            ))}
          </ul>
        </SectionCard>
        <SectionCard title="Coming soon">
          <p className="text-sm text-muted">
            The employees roster arrives in an upcoming release. Its entry is
            already in the sidebar so the navigation is stable.
          </p>
        </SectionCard>
      </div>

      <FounderCharts />
    </AppShell>
  );
}
