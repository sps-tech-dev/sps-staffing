"use client";
import { useEffect, useState } from "react";
import {
  DndContext, DragEndEvent, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors,
} from "@dnd-kit/core";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useJobs, useJobPipeline, useChangeStage } from "@/lib/api/hooks";
import { AiInsightsCard } from "@/components/ai/ai-insights-card";
import type { PipelineRow } from "@/lib/api/types";
import { KanbanSquare } from "lucide-react";

// Active pipeline columns (Part 5). Drag a candidate card between columns to move
// its stage; illegal transitions are rejected by the server (409) and revert.
const COLUMNS = ["sourced", "screened", "assessed", "submitted", "interview", "offer", "placed"];

function Card({ row }: { row: PipelineRow }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: row.id, data: { stage: row.stage } });
  return (
    <div
      ref={setNodeRef} {...listeners} {...attributes}
      className={`cursor-grab rounded-lg bg-page px-3 py-2 text-sm text-ink shadow-sm ${isDragging ? "opacity-50" : ""}`}
    >
      {row.candidate.full_name}
    </div>
  );
}

function Column({ stage, rows }: { stage: string; rows: PipelineRow[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  return (
    <div ref={setNodeRef}
      className={`rounded-xl border bg-card p-3 ${isOver ? "border-[#1B5FE8] ring-2 ring-[#1B5FE8]/30" : "border-cardline"}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">{stage}</span>
        <span className="text-xs text-muted">{rows.length}</span>
      </div>
      <div className="space-y-2">
        {rows.length === 0 ? <p className="py-3 text-center text-xs text-muted">—</p>
          : rows.map((r) => <Card key={r.id} row={r} />)}
      </div>
    </div>
  );
}

export default function PipelinePage() {
  const { data: jobs } = useJobs();
  const [jobId, setJobId] = useState<string | null>(null);
  useEffect(() => { if (!jobId && jobs && jobs.length) setJobId(jobs[0].id); }, [jobs, jobId]);

  const { data: pipe, isLoading } = useJobPipeline(jobId);
  const firstCandidateId = pipe ? (Object.values(pipe.stages).flat()[0]?.candidate_id ?? null) : null;
  const changeStage = useChangeStage(jobId);
  const [error, setError] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }), useSensor(KeyboardSensor));

  function onDragEnd(e: DragEndEvent) {
    const appId = String(e.active.id);
    const from = String(e.active.data.current?.stage ?? "");
    const to = e.over ? String(e.over.id) : "";
    if (!to || to === from) return;
    setError(null);
    changeStage.mutate({ appId, stage: to }, {
      onError: () => setError(`Can't move ${from} → ${to} (not a valid pipeline transition).`),
    });
  }

  return (
    <AppShell role="client" title="Pipeline">
      <SectionCard title="Select job">
        {!jobs || jobs.length === 0 ? (
          <EmptyState icon={<KanbanSquare size={28} />} title="No jobs yet" hint="Post a job to build a pipeline." />
        ) : (
          <select value={jobId ?? ""} onChange={(e) => setJobId(e.target.value)}
            className="w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8] sm:max-w-md">
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
          </select>
        )}
      </SectionCard>

      {/* F6: gated AI widget — renders only when the `ai` flag is on (off by default). */}
      <AiInsightsCard candidateId={firstCandidateId} />

      {error && <p role="alert" className="mt-4 rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">{error}</p>}

      {jobId && (
        <div className="mt-6">
          {isLoading || !pipe ? (
            <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-7">
              {COLUMNS.map((c) => <Skeleton key={c} className="h-28" />)}
            </div>
          ) : (
            <DndContext sensors={sensors} onDragEnd={onDragEnd}>
              <div className="grid grid-flow-col auto-cols-[minmax(180px,1fr)] gap-3 overflow-x-auto pb-2 xl:grid-flow-row xl:grid-cols-7">
                {COLUMNS.map((stage) => <Column key={stage} stage={stage} rows={pipe.stages[stage] ?? []} />)}
              </div>
            </DndContext>
          )}
        </div>
      )}
    </AppShell>
  );
}
