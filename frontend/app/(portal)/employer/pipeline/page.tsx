"use client";
import { useEffect, useState } from "react";
import {
  DndContext, DragEndEvent, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors,
} from "@dnd-kit/core";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import {
  useJobs, useJobPipeline, useTransitionStage, useCreateSubmission, useCreateOffer,
  useCreateInterview, useCandidateTimeline,
} from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import { AiInsightsCard } from "@/components/ai/ai-insights-card";
import type { PipelineRow } from "@/lib/api/types";
import {
  KanbanSquare, Send, FileSignature, CalendarClock, ShieldAlert, PauseCircle,
  XCircle, RotateCcw, X, Hourglass,
} from "lucide-react";

// F2b: columns speak the B.5 vocabulary (D5 closed in F1); stage changes are
// OPTIMISTIC-LOCKED via POST /transition + expected_version (the PATCH shim is
// RETIRED). The state machine is NOT reimplemented here — the server guard
// answers 409 (ILLEGAL_TRANSITION / STALE_STATE / RTR_REQUIRED / reason errors)
// and the UI surfaces each cleanly.
const COLUMNS = [
  "applied", "screening", "aptitude_test", "aptitude_passed", "internal_interview",
  "internal_passed", "rtr_pending", "submitted_to_client", "client_round_1",
  "client_round_2", "client_round_3", "offer", "offer_accepted", "joined",
];
const TAIL_COLUMNS = ["guarantee", "invoiced", "paid", "on_hold", "withdrawn", "dropped", "aptitude_failed"];
const LABEL: Record<string, string> = {
  applied: "Applied", screening: "Screening", aptitude_test: "Aptitude Test",
  aptitude_passed: "Aptitude Passed", aptitude_failed: "Aptitude Failed",
  internal_interview: "Internal Interview", internal_passed: "Internal Passed",
  rtr_pending: "RTR Pending", submitted_to_client: "Submitted to Client",
  client_round_1: "Client Round 1", client_round_2: "Client Round 2",
  client_round_3: "Client Round 3", offer: "Offer", offer_accepted: "Offer Accepted",
  joined: "Joined", guarantee: "Guarantee", invoiced: "Invoiced", paid: "Paid",
  on_hold: "On Hold", withdrawn: "Withdrawn", dropped: "Dropped",
};
const REASON_MOVES: { to: string; label: string }[] = [
  { to: "dropped", label: "Drop" },
  { to: "withdrawn", label: "Withdraw" },
];

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    switch (e.code) {
      case "STALE_STATE":
        return "The board changed elsewhere — it has been refreshed. Please retry your move.";
      case "ILLEGAL_TRANSITION":
        return e.message || "That move isn't a valid pipeline transition.";
      case "RTR_REQUIRED":
        return "RTR consent is required before submitting to the client. Collect the candidate's RTR first.";
      case "REASON_REQUIRED":
      case "VALIDATION_ERROR":
        return e.message || "A reason is required for this move.";
      default:
        return e.message || "The move was rejected.";
    }
  }
  return "The move failed — please retry.";
}

type CardHandlers = {
  onSubmit: (r: PipelineRow) => void; onOffer: (id: string) => void;
  onInterview: (id: string) => void; onReasonMove: (r: PipelineRow, to: string, label: string) => void;
  onHold: (r: PipelineRow) => void; onOpen: (r: PipelineRow) => void;
};

function Card({ row, busy, h }: { row: PipelineRow; busy: boolean; h: CardHandlers }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: row.id, data: { stage: row.stage, version: row.version },
  });
  const rtrBlocked = row.stage === "rtr_pending";
  return (
    <div className={`rounded-lg bg-page px-3 py-2 text-sm text-ink shadow-sm ${isDragging ? "opacity-50" : ""}`}>
      <div className="flex items-start justify-between gap-1">
        <div ref={setNodeRef} {...listeners} {...attributes} className="cursor-grab">
          {row.candidate.full_name}
        </div>
        <button type="button" onClick={() => h.onOpen(row)} title="Open details"
          className="rounded p-0.5 text-muted hover:bg-white hover:text-sps-blue">
          <KanbanSquare size={13} />
        </button>
      </div>
      {rtrBlocked && (
        <p className="mt-1 inline-flex items-center gap-1 rounded bg-[#FFFBEB] px-1.5 py-0.5 text-[10px] font-medium text-[#D97706]">
          <ShieldAlert size={10} /> RTR required before submit
        </p>
      )}
      <div className="mt-1 flex flex-wrap gap-2">
        <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={() => h.onSubmit(row)}
          disabled={busy || rtrBlocked}
          title={rtrBlocked ? "Blocked: collect the candidate's RTR consent first" : "Submit to client"}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#1B5FE8] hover:underline disabled:cursor-not-allowed disabled:opacity-40">
          <Send size={11} /> Submit
        </button>
        <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={() => h.onInterview(row.id)} disabled={busy}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#7C3AED] hover:underline disabled:opacity-50" title="Schedule an interview">
          <CalendarClock size={11} /> Interview
        </button>
        <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={() => h.onOffer(row.id)} disabled={busy}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#16A34A] hover:underline disabled:opacity-50" title="Create a draft offer">
          <FileSignature size={11} /> Offer
        </button>
        <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={() => h.onHold(row)} disabled={busy}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[#D97706] hover:underline disabled:opacity-50" title="Put on hold">
          <PauseCircle size={11} /> Hold
        </button>
        {REASON_MOVES.map((m) => (
          <button key={m.to} type="button" onPointerDown={(e) => e.stopPropagation()}
            onClick={() => h.onReasonMove(row, m.to, m.label)} disabled={busy}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-[#DC2626] hover:underline disabled:opacity-50"
            title={`${m.label} (reason required)`}>
            <XCircle size={11} /> {m.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Column({ stage, rows, busy, h }: {
  stage: string; rows: PipelineRow[]; busy: boolean; h: CardHandlers;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  return (
    <div ref={setNodeRef}
      className={`rounded-xl border bg-card p-3 ${isOver ? "border-[#1B5FE8] ring-2 ring-[#1B5FE8]/30" : "border-cardline"}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">{LABEL[stage] ?? stage}</span>
        <span className="text-xs text-muted">{rows.length}</span>
      </div>
      <div className="space-y-2">
        {rows.length === 0 ? <p className="py-3 text-center text-xs text-muted">—</p>
          : rows.map((r) => <Card key={r.id} row={r} busy={busy} h={h} />)}
      </div>
    </div>
  );
}

/** Reason modal for drop/withdraw — the guard requires a reason; we collect it
 *  up front instead of bouncing off the server's 422. */
function ReasonModal({ open, label, onCancel, onConfirm }: {
  open: boolean; label: string; onCancel: () => void; onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  useEffect(() => { if (open) setReason(""); }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-sm rounded-2xl border border-cardline bg-card p-5 shadow-lg">
        <h3 className="font-display text-base font-bold text-ink">{label} — reason required</h3>
        <p className="mt-1 text-xs text-muted">The pipeline guard records why a candidate leaves the process.</p>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} autoFocus
          placeholder="e.g. candidate accepted another offer"
          className="mt-3 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-page">Cancel</button>
          <button onClick={() => onConfirm(reason)} disabled={!reason.trim()}
            className="rounded-lg bg-[#DC2626] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#b91c1c] disabled:opacity-40">
            Confirm {label.toLowerCase()}
          </button>
        </div>
      </div>
    </div>
  );
}

/** F2b stage side-panel: candidate context + live stage/version + the append-only
 *  timeline. Deep actions are their own later slices — marked in-panel. */
function SidePanel({ row, onClose }: { row: PipelineRow | null; onClose: () => void }) {
  const { data: timeline, isLoading } = useCandidateTimeline(row?.candidate_id ?? null);
  if (!row) return null;
  return (
    <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-md overflow-y-auto border-l border-cardline bg-card p-5 shadow-xl">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-display text-lg font-bold text-ink">{row.candidate.full_name}</h2>
          <p className="text-xs text-muted">{row.candidate.email ?? "no email on file"}</p>
        </div>
        <button onClick={onClose} aria-label="Close" className="rounded-lg p-1.5 text-muted hover:bg-page"><X size={18} /></button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <StatusPill status={LABEL[row.stage] ?? row.stage} />
        <span className="text-[11px] text-muted">version {row.version}</span>
        {typeof row.candidate.total_exp === "number" && (
          <span className="text-[11px] text-muted">{row.candidate.total_exp} yrs exp</span>
        )}
      </div>
      {row.candidate.skills && row.candidate.skills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {row.candidate.skills.map((s) => (
            <span key={s} className="rounded-full bg-page px-2 py-0.5 text-[11px] text-ink">{s}</span>
          ))}
        </div>
      )}
      <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-muted">Timeline</h3>
      <div className="mt-2 space-y-2">
        {isLoading ? <Skeleton className="h-20" /> :
          !timeline || timeline.length === 0 ? (
            <p className="text-sm text-muted">No events yet.</p>
          ) : (
            timeline.slice().reverse().map((e, i) => (
              <div key={i} className="rounded-lg border border-cardline bg-page px-3 py-2">
                <p className="text-xs font-medium text-ink">{e.event_type}</p>
                <p className="text-[11px] text-muted">{new Date(e.occurred_at).toLocaleString()}</p>
              </div>
            ))
          )}
      </div>
      <div className="mt-6 rounded-xl border border-dashed border-cardline p-4">
        <p className="inline-flex items-center gap-1.5 text-xs text-muted">
          <Hourglass size={13} /> Assessment issue, interview scheduling and offer
          deep-actions open here in upcoming releases.
        </p>
      </div>
    </aside>
  );
}

export default function PipelinePage() {
  const { data: jobs } = useJobs();
  const [jobId, setJobId] = useState<string | null>(null);
  useEffect(() => { if (!jobId && jobs && jobs.length) setJobId(jobs[0].id); }, [jobs, jobId]);

  const { data: pipe, isLoading } = useJobPipeline(jobId);
  const firstCandidateId = pipe ? (Object.values(pipe.stages).flat()[0]?.candidate_id ?? null) : null;
  const transition = useTransitionStage(jobId);
  const createSub = useCreateSubmission();
  const createOffer = useCreateOffer();
  const createInterview = useCreateInterview();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reasonFor, setReasonFor] = useState<{ row: PipelineRow; to: string; label: string } | null>(null);
  const [selected, setSelected] = useState<PipelineRow | null>(null);

  function doTransition(row: PipelineRow, toStage: string, reason?: string) {
    setError(null); setNotice(null);
    transition.mutate(
      { appId: row.id, toStage, expectedVersion: row.version, reason },
      {
        onError: (e) => setError(errorMessage(e)),
        onSuccess: () => setNotice(`Moved to ${LABEL[toStage] ?? toStage}.`),
      },
    );
  }

  function onDragEnd(e: DragEndEvent) {
    const appId = String(e.active.id);
    const from = String(e.active.data.current?.stage ?? "");
    const to = e.over ? String(e.over.id) : "";
    if (!to || to === from) return;
    const row = Object.values(pipe?.stages ?? {}).flat().find((r) => r.id === appId);
    if (!row) return;
    doTransition(row, to);
  }

  function onSubmitToClient(row: PipelineRow) {
    setNotice(null); setError(null);
    createSub.mutate(row.id, {
      onSuccess: () => setNotice("Candidate submitted to client. Track it under Submissions."),
      onError: (e) => setError(errorMessage(e)),
    });
  }
  function onMakeOffer(appId: string) {
    setNotice(null); setError(null);
    createOffer.mutate(appId, {
      onSuccess: () => setNotice("Draft offer created. Set CTC / joining date under Offers."),
      onError: (e) => setError(errorMessage(e)),
    });
  }
  function onScheduleInterview(appId: string) {
    setNotice(null); setError(null);
    createInterview.mutate(appId, {
      onSuccess: () => setNotice("Interview created. Set the time/mode under Interviews."),
      onError: (e) => setError(errorMessage(e)),
    });
  }

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }), useSensor(KeyboardSensor));
  const busy = transition.isPending || createSub.isPending || createOffer.isPending || createInterview.isPending;
  const handlers: CardHandlers = {
    onSubmit: onSubmitToClient,
    onOffer: onMakeOffer,
    onInterview: onScheduleInterview,
    onHold: (r) => doTransition(r, "on_hold"),
    onReasonMove: (row, to, label) => setReasonFor({ row, to, label }),
    onOpen: (r) => setSelected(r),
  };

  return (
    <AppShell role="employee" title="Pipeline">
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
            <div className="grid grid-flow-col auto-cols-[minmax(180px,1fr)] gap-3 overflow-x-auto pb-2">
              {COLUMNS.map((c) => <Skeleton key={c} className="h-28" />)}
            </div>
          ) : (
            <DndContext sensors={sensors} onDragEnd={onDragEnd}>
              <div className="grid grid-flow-col auto-cols-[minmax(190px,220px)] gap-3 overflow-x-auto pb-2">
                {COLUMNS.map((stage) => (
                  <Column key={stage} stage={stage} rows={pipe.stages[stage] ?? []} busy={busy} h={handlers} />
                ))}
              </div>
            </DndContext>
          )}
          {!isLoading && pipe && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Post-join & closed</p>
              <div className="grid grid-flow-col auto-cols-[minmax(160px,200px)] gap-3 overflow-x-auto pb-2">
                {TAIL_COLUMNS.map((stage) => (
                  <div key={stage} className="rounded-xl border border-cardline bg-card p-3 opacity-90">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted">{LABEL[stage] ?? stage}</span>
                      <span className="text-xs text-muted">{(pipe.stages[stage] ?? []).length}</span>
                    </div>
                    <div className="space-y-2">
                      {(pipe.stages[stage] ?? []).length === 0
                        ? <p className="py-2 text-center text-xs text-muted">—</p>
                        : (pipe.stages[stage] ?? []).map((r) => (
                          <div key={r.id} className="rounded-lg bg-page px-3 py-2 text-sm text-ink">
                            <div className="flex items-center justify-between gap-1">
                              <span>{r.candidate.full_name}</span>
                              {stage === "on_hold" && (
                                <button type="button" onClick={() => doTransition(r, "screening")}
                                  title="Reopen into the pipeline (the server rejects illegal targets)"
                                  className="inline-flex items-center gap-1 text-[11px] font-medium text-[#1B5FE8] hover:underline">
                                  <RotateCcw size={11} /> Reopen
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <ReasonModal open={!!reasonFor} label={reasonFor?.label ?? ""}
        onCancel={() => setReasonFor(null)}
        onConfirm={(reason) => {
          if (reasonFor) doTransition(reasonFor.row, reasonFor.to, reason);
          setReasonFor(null);
        }} />
      <SidePanel row={selected} onClose={() => setSelected(null)} />
    </AppShell>
  );
}
