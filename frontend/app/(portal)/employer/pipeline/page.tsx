"use client";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useJobs, useJobPipeline } from "@/lib/api/hooks";
import { KanbanSquare } from "lucide-react";

// Read-only pipeline view (Slice 3). Drag-drop kanban arrives in Slice 4 (@dnd-kit).
const COLUMNS = ["sourced", "screened", "assessed", "submitted", "interview", "offer", "placed"];

export default function PipelinePage() {
  const { data: jobs } = useJobs();
  const [jobId, setJobId] = useState<string | null>(null);
  useEffect(() => {
    if (!jobId && jobs && jobs.length) setJobId(jobs[0].id);
  }, [jobs, jobId]);
  const { data: pipe, isLoading } = useJobPipeline(jobId);

  return (
    <AppShell role="client" title="Pipeline">
      <SectionCard title="Select job">
        {!jobs || jobs.length === 0 ? (
          <EmptyState icon={<KanbanSquare size={28} />} title="No jobs yet" hint="Post a job to build a pipeline." />
        ) : (
          <select
            value={jobId ?? ""} onChange={(e) => setJobId(e.target.value)}
            className="w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8] sm:max-w-md"
          >
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
          </select>
        )}
      </SectionCard>

      {jobId && (
        <div className="mt-6">
          {isLoading || !pipe ? (
            <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-7">
              {COLUMNS.map((c) => <Skeleton key={c} className="h-28" />)}
            </div>
          ) : (
            <div className="grid grid-flow-col auto-cols-[minmax(180px,1fr)] gap-3 overflow-x-auto pb-2 xl:grid-flow-row xl:grid-cols-7">
              {COLUMNS.map((stage) => {
                const rows = pipe.stages[stage] ?? [];
                return (
                  <div key={stage} className="rounded-xl border border-cardline bg-card p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted">{stage}</span>
                      <span className="text-xs text-muted">{rows.length}</span>
                    </div>
                    <div className="space-y-2">
                      {rows.length === 0 ? (
                        <p className="py-3 text-center text-xs text-muted">—</p>
                      ) : rows.map((r) => (
                        <div key={r.id} className="rounded-lg bg-page px-3 py-2 text-sm text-ink">{r.candidate.full_name}</div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}
