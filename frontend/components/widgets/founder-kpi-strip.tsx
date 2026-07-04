"use client";
import { IndianRupee, Briefcase, Users, Award } from "lucide-react";
import { KpiGrid } from "@/components/widgets/kpi-grid";
import { useFounderOverview } from "@/lib/api/hooks";

const inr = (n: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);

/** F1: founder KPI strip on the admin dashboard. Renders ONLY when the session's
 *  role passes the backend founder gate (owner/super_admin) — a plain admin gets
 *  a 403 from /api/dashboard/founder/overview and the strip silently disappears
 *  (the query errors → we render null). A 403 must never break the dashboard. */
export function FounderKpiStrip() {
  const { data, isError, isLoading } = useFounderOverview();
  if (isError || (!isLoading && !data)) return null;
  if (isLoading) return null;
  const d = data!;
  return (
    <section aria-label="Founder KPIs" className="mb-6">
      <h2 className="mb-3 font-display text-sm font-bold uppercase tracking-wide text-muted">
        Founder view · this month
      </h2>
      <KpiGrid items={[
        { value: inr(d.revenue_mtd), label: "Revenue (MTD)", icon: <IndianRupee size={20} />, accent: "#16A34A" },
        { value: d.open_jobs, label: "Open jobs", icon: <Briefcase size={20} />, accent: "#1B5FE8" },
        { value: d.pipeline_active, label: "Active in pipeline", icon: <Users size={20} />, accent: "#7C3AED" },
        { value: d.placements_total, label: "Placements", icon: <Award size={20} />, accent: "#E8A020" },
      ]} />
    </section>
  );
}
