"use client";
import { useEffect, useState } from "react";
import {
  DndContext, DragEndEvent, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors,
} from "@dnd-kit/core";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useJobs, useJobPipeline, useChangeStage, useCreateSubmission, useCreateOffer, useCreateInterview } from "@/lib/api/hooks";
import { AiInsightsCard } from "@/components/ai/ai-insights-card";
import type { PipelineRow } from "@/lib/api/types";
import { KanbanSquare, Send, FileSignature, CalendarClock } from "lucide-react";

// Active pipeline columns (Part 5). Drag a candidate card between columns to move
// its stage; illegal transitions are rejected by the server (409) and revert.
const COLUMNS = ["sourced", "screened", "assessed", "submitted", "interview", "offer", "placed"];

function Card({ row, onSubmit, onOffer, onInterview, busy }: {
  row: PipelineRow; onSubmit: (id: string) => void; onOffer: (id: string) => void;
  onInterview: (id: string) => void; busy: boolean;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: row.id, data: { stage: row.stage } });
  return (
    <div className={`rounded-lg bg-page px-3 py-2 text-sm text-ink shadow-sm ${isDragging ? "opacity-50" : ""}`}>
      <div ref={setNodeRef} {...listeners} {...attributes} className="cursor-grab">
        {row.candidate.full_name}
      </div>
      <div className="mt-1 flex flex-wrap gap-2">
        <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={() => onSubmit(row.id)} disabled={busy}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#1B5FE8] hover:underline disabled:opacity-50" title="Submit to client">
          <Send size={11} /> Submit
        </button>
        <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={() => onInterview(row.id)} disabled={busy}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#7C3AED] hover:underline disabled:opacity-50" title="Schedule an interview">
          <CalendarClock size={11} /> Interview
        </button>
        <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={() => onOffer(row.id)} disabled={busy}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#16A34A] hover:underline disabled:opacity-50" title="Create a draft offer">
          <FileSignature size={11} /> Offer
        </button>
      </div>
    </div>
  );
}

function Column({ stage, rows, onSubmit, onOffer, onInterview, busy }: {
  stage: string; rows: PipelineRow[]; onSubmit: (id: string) => void; onOffer: (id: string) => void;
  onInterview: (id: string) => void; busy: boolean;
}) {
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
          : rows.map((r) => <Card key={r.id} row={r} onSubmit={onSubmit} onOffer={onOffer} onInterview={onInterview} busy={busy} />)}
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
  const createSub = useCreateSubmission();
  const createOffer = useCreateOffer();
  const createInterview = useCreateInterview();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function onScheduleInterview(appId: string) {
    setNotice(null); setError(null);
    createInterview.mutate(appId, {
      onSuccess: () => setNotice("Interview created. Set the time/mode under Interviews."),
      onError: () => setError("Couldn't schedule the interview — please retry."),
    });
  }

  function onSubmitToClient(appId: string) {
    setNotice(null); setError(null);
    createSub.mutate(appId, {
      onSuccess: () => setNotice("Candidate submitted to client. Track it under Submissions."),
      onError: () => setError("Couldn't submit to client — please retry."),
    });
  }
  function onMakeOffer(appId: string) {
    setNotice(null); setError(null);
    createOffer.mutate(appId, {
      onSuccess: () => setNotice("Draft offer created. Set CTC / joining date under Offers."),
      onError: () => setError("Couldn't create the offer — please retry."),
    });
  }
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
      {notice && <p className="mt-4 rounded-lg bg-[#F0FDF4] px-3 py-2 text-sm text-[#16A34A]">{notice}</p>}

      {jobId && (
        <div className="mt-6">
          {isLoading || !pipe ? (
            <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-7">
              {COLUMNS.map((c) => <Skeleton key={c} className="h-28" />)}
            </div>
          ) : (
            <DndContext sensors={sensors} onDragEnd={onDragEnd}>
              <div className="grid grid-flow-col auto-cols-[minmax(180px,1fr)] gap-3 overflow-x-auto pb-2 xl:grid-flow-row xl:grid-cols-7">
                {COLUMNS.map((stage) => (
                  <Column key={stage} stage={stage} rows={pipe.stages[stage] ?? []}
                          onSubmit={onSubmitToClient} onOffer={onMakeOffer} onInterview={onScheduleInterview}
                          busy={createSub.isPending || createOffer.isPending || createInterview.isPending} />
                ))}
              </div>
            </DndContext>
          )}
        </div>
      )}
    </AppShell>
  );
}
