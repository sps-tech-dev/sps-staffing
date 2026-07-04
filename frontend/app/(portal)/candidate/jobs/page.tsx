"use client";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useBrowseJobs, useMyApplications } from "@/lib/api/hooks";
import { Briefcase, CheckCircle2 } from "lucide-react";

/** F3b: open roles + which ones this candidate ALREADY has applications for
 *  (real cross-ref via /me/applications). Applications are PLACED BY STAFF in
 *  this platform (POST /applications is staff-gated by design) — so there is no
 *  self-serve Apply button; the affordance is honest guidance instead. */
export default function BrowseJobsPage() {
  const { data: jobs, isLoading, isError } = useBrowseJobs();
  const { data: mine } = useMyApplications();
  const appliedJobIds = new Set((mine ?? []).map((a) => a.job_id));
  return (
    <AppShell role="candidate" title="Browse Jobs">
      <SectionCard title="Open roles">
        {isLoading ? (
          <Skeleton className="h-32" />
        ) : isError ? (
          <p role="alert" className="rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">
            Couldn&apos;t load open roles — please refresh.
          </p>
        ) : !jobs || jobs.length === 0 ? (
          <EmptyState icon={<Briefcase size={28} />} title="No open roles right now"
            hint="New roles from our clients appear here — check back soon." />
        ) : (
          <div className="divide-y divide-cardline">
            {jobs.map((j) => (
              <div key={j.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <p className="text-sm font-medium text-ink">{j.title}</p>
                  <p className="text-xs text-muted">
                    {(j.skills ?? []).slice(0, 5).join(" · ") || "See details with your recruiter"}
                    {j.min_exp != null && ` · ${j.min_exp}${j.max_exp != null ? `–${j.max_exp}` : "+"} yrs`}
                  </p>
                </div>
                {appliedJobIds.has(j.id) ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#F0FDF4] px-2.5 py-1 text-[11px] font-semibold text-[#16A34A]">
                    <CheckCircle2 size={12} /> Applied
                  </span>
                ) : (
                  <span className="text-[11px] text-muted">Interested? Our recruiting team places applications for you.</span>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </AppShell>
  );
}
