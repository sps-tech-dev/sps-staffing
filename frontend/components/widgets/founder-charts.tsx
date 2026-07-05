"use client";
import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { SectionCard } from "@/components/kit/section-card";
import { Skeleton } from "@/components/kit/skeleton";
import { useFounderByBu, useFounderOverview, useFounderTrends } from "@/lib/api/hooks";

// F7: founder trend charts. Owner/super_admin/founder ONLY — gated the SAME way
// as the F1 KPI strip: it probes /dashboard/founder/overview first and renders
// NOTHING for a plain admin (whose 403 resolves this to null). No broken page.
const TREND_METRICS = [
  { key: "revenue", label: "Revenue", money: true },
  { key: "placements", label: "Placements", money: false },
  { key: "applications", label: "Applications", money: false },
] as const;

const inr = (n: number) =>
  new Intl.NumberFormat("en-IN", { notation: "compact", style: "currency", currency: "INR", maximumFractionDigits: 1 }).format(n);

function TrendChart() {
  const [metric, setMetric] = useState<(typeof TREND_METRICS)[number]>(TREND_METRICS[0]);
  const { data, isLoading } = useFounderTrends(metric.key, 6);
  const rows = data ? Object.entries(data.series).map(([month, value]) => ({ month, value })) : [];
  return (
    <SectionCard title="Trends · last 6 months">
      <div className="mb-3 flex flex-wrap gap-1.5">
        {TREND_METRICS.map((m) => (
          <button key={m.key} onClick={() => setMetric(m)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${metric.key === m.key ? "bg-sps-blue text-white" : "bg-page text-muted hover:text-ink"}`}>
            {m.label}
          </button>
        ))}
      </div>
      {isLoading ? <Skeleton className="h-56" /> : (
        <ResponsiveContainer width="100%" height={224}>
          <LineChart data={rows} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#EAEEF3" />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#6B7689" }} />
            <YAxis tick={{ fontSize: 11, fill: "#6B7689" }}
              tickFormatter={(v) => (metric.money ? inr(v) : String(v))} width={metric.money ? 56 : 32} />
            <Tooltip formatter={(v: number) => (metric.money ? inr(v) : v)} />
            <Line type="monotone" dataKey="value" stroke="#1B5FE8" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </SectionCard>
  );
}

function ByBuChart() {
  const { data, isLoading } = useFounderByBu();
  const rows = data
    ? Object.entries(data).map(([bu, v]) => ({
        bu: bu.charAt(0) + bu.slice(1).toLowerCase(), placements: v.placements, applications: v.applications,
      }))
    : [];
  return (
    <SectionCard title="By business unit">
      <p className="mb-3 text-xs text-muted">
        Academy and Consulting read zero until those verticals launch — real queries, not fabricated.
      </p>
      {isLoading ? <Skeleton className="h-56" /> : (
        <ResponsiveContainer width="100%" height={224}>
          <BarChart data={rows} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#EAEEF3" />
            <XAxis dataKey="bu" tick={{ fontSize: 11, fill: "#6B7689" }} />
            <YAxis tick={{ fontSize: 11, fill: "#6B7689" }} width={32} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="applications" fill="#5B8FFF" radius={[3, 3, 0, 0]} />
            <Bar dataKey="placements" fill="#1B5FE8" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </SectionCard>
  );
}

export function FounderCharts() {
  // gate probe — identical pattern to F1's FounderKpiStrip: a plain admin's 403
  // resolves !data → render nothing (graceful, no broken page).
  const { data, isError, isLoading } = useFounderOverview();
  if (isError || (!isLoading && !data)) return null;
  if (isLoading) return null;
  return (
    <section aria-label="Founder trends" className="mt-6">
      <h2 className="mb-3 font-display text-sm font-bold uppercase tracking-wide text-muted">
        Founder view · trends
      </h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <TrendChart />
        <ByBuChart />
      </div>
    </section>
  );
}
