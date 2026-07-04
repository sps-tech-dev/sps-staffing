"use client";
import { useState } from "react";
import {
  DndContext, DragEndEvent, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors,
} from "@dnd-kit/core";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import {
  useConvertLead, useCreateLead, useLeadActivities, useLeads, useLeadTransition, useLogActivity,
} from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import type { ConvertResult, Lead } from "@/lib/api/types";
import { FileText, X, XCircle, ArrowRightCircle, Building2, CheckCircle2 } from "lucide-react";

// F6: the lead board mirrors the B.12 mini guard EXACTLY — linear forward path,
// lost from any non-terminal WITH a reason, won/lost terminal. The guard is the
// server's; illegal moves surface its 409, we never pre-empt it beyond UX.
const ACTIVE_COLS = ["new", "qualified", "proposal", "negotiation"];
const TERMINAL_COLS = ["won", "lost"];
const LABEL: Record<string, string> = {
  new: "New", qualified: "Qualified", proposal: "Proposal",
  negotiation: "Negotiation", won: "Won", lost: "Lost",
};

function errText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "ILLEGAL_TRANSITION") return e.message || "That stage move isn't allowed.";
    if (e.code === "REASON_REQUIRED") return "A reason is required to mark a lead lost.";
    return e.message || "The action was rejected.";
  }
  return "The action failed — please retry.";
}

function LeadCard({ lead, onOpen, onLost, onConvert, busy }: {
  lead: Lead; onOpen: (l: Lead) => void; onLost: (l: Lead) => void;
  onConvert: (l: Lead) => void; busy: boolean;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: lead.id, data: { stage: lead.stage },
  });
  const terminal = lead.stage === "won" || lead.stage === "lost";
  return (
    <div className={`rounded-lg bg-page px-3 py-2 text-sm text-ink shadow-sm ${isDragging ? "opacity-50" : ""}`}>
      <div className="flex items-start justify-between gap-1">
        <div ref={terminal ? undefined : setNodeRef} {...(terminal ? {} : { ...listeners, ...attributes })}
          className={terminal ? "" : "cursor-grab"}>
          <p className="font-medium">{lead.company}</p>
          {lead.contact_name && <p className="text-[11px] text-muted">{lead.contact_name}</p>}
        </div>
        <button type="button" onClick={() => onOpen(lead)} title="Activities & details"
          className="rounded p-0.5 text-muted hover:bg-white hover:text-sps-blue"><FileText size={13} /></button>
      </div>
      {lead.stage === "lost" && lead.lost_reason && (
        <p className="mt-1 text-[11px] text-muted">“{lead.lost_reason}”</p>
      )}
      <div className="mt-1 flex flex-wrap gap-2">
        {lead.stage === "won" && (
          lead.converted_client_id ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#16A34A]">
              <CheckCircle2 size={11} /> Converted to client
            </span>
          ) : (
            <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={() => onConvert(lead)} disabled={busy}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-[#16A34A] hover:underline disabled:opacity-50">
              <Building2 size={11} /> Convert to client
            </button>
          )
        )}
        {!terminal && (
          <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={() => onLost(lead)} disabled={busy}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-[#DC2626] hover:underline disabled:opacity-50"
            title="Mark lost (reason required)">
            <XCircle size={11} /> Lost
          </button>
        )}
      </div>
    </div>
  );
}

function Column({ stage, leads, busy, handlers, droppable }: {
  stage: string; leads: Lead[]; busy: boolean; droppable: boolean;
  handlers: { onOpen: (l: Lead) => void; onLost: (l: Lead) => void; onConvert: (l: Lead) => void };
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage, disabled: !droppable });
  return (
    <div ref={setNodeRef}
      className={`rounded-xl border bg-card p-3 ${isOver ? "border-[#1B5FE8] ring-2 ring-[#1B5FE8]/30" : "border-cardline"}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">{LABEL[stage]}</span>
        <span className="text-xs text-muted">{leads.length}</span>
      </div>
      <div className="space-y-2">
        {leads.length === 0 ? <p className="py-3 text-center text-xs text-muted">—</p>
          : leads.map((l) => <LeadCard key={l.id} lead={l} busy={busy} {...handlers} />)}
      </div>
    </div>
  );
}

function LostModal({ lead, onCancel, onConfirm }: {
  lead: Lead; onCancel: () => void; onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-sm rounded-2xl border border-cardline bg-card p-5 shadow-lg">
        <h3 className="font-display text-base font-bold text-ink">Mark “{lead.company}” lost — reason required</h3>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} autoFocus
          placeholder="e.g. chose a competitor / budget cut"
          className="mt-3 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-page">Cancel</button>
          <button onClick={() => onConfirm(reason)} disabled={!reason.trim()}
            className="rounded-lg bg-[#DC2626] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">
            Confirm lost
          </button>
        </div>
      </div>
    </div>
  );
}

/** Convert modal — shows the IDEMPOTENT already-converted state honestly: a
 *  second convert returns the SAME client, and the UI says so. */
function ConvertModal({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const convert = useConvertLead();
  const [jobTitle, setJobTitle] = useState("");
  const [result, setResult] = useState<ConvertResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-md rounded-2xl border border-cardline bg-card p-5 shadow-lg">
        <h3 className="font-display text-base font-bold text-ink">Convert “{lead.company}” to a client</h3>
        {result ? (
          <div className="mt-3 rounded-lg bg-[#F0FDF4] p-3 text-sm text-ink">
            <p className="font-medium text-[#16A34A]">
              {result.already_converted ? "Already converted — this is the existing client." : "Client created."}
            </p>
            <p className="mt-1 font-mono text-xs text-muted">client {result.client_id.slice(0, 8)}…</p>
            {result.job_id && <p className="font-mono text-xs text-muted">job intake {result.job_id.slice(0, 8)}…</p>}
          </div>
        ) : (
          <>
            <label className="mt-3 block text-xs text-muted">Optional job intake title
              <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)}
                placeholder="e.g. Platform Engineer"
                className="mt-1 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
            </label>
            {err && <p role="alert" className="mt-2 text-xs text-[#DC2626]">{err}</p>}
          </>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-page">
            {result ? "Done" : "Cancel"}
          </button>
          {!result && (
            <button disabled={convert.isPending}
              onClick={() => convert.mutate({ id: lead.id, job_title: jobTitle.trim() || undefined },
                { onSuccess: setResult, onError: (e) => setErr(errText(e)) })}
              className="rounded-lg bg-[#16A34A] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">
              {convert.isPending ? "Converting…" : "Convert"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function LeadPanel({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const { data: acts, isLoading } = useLeadActivities(lead.id);
  const log = useLogActivity();
  const [type, setType] = useState("call");
  const [notes, setNotes] = useState("");
  return (
    <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-md overflow-y-auto border-l border-cardline bg-card p-5 shadow-xl">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-display text-lg font-bold text-ink">{lead.company}</h2>
          <p className="text-xs text-muted">
            {lead.contact_name ?? "no contact"} {lead.contact_email && `· ${lead.contact_email}`}
            {lead.source && ` · via ${lead.source}`}
          </p>
        </div>
        <button onClick={onClose} aria-label="Close" className="rounded-lg p-1.5 text-muted hover:bg-page"><X size={18} /></button>
      </div>
      <form className="mt-4 flex flex-wrap items-end gap-2"
        onSubmit={(e) => { e.preventDefault(); log.mutate({ id: lead.id, type, notes: notes || undefined },
          { onSuccess: () => setNotes("") }); }}>
        <label className="text-xs text-muted">Type
          <select value={type} onChange={(e) => setType(e.target.value)}
            className="mt-1 block rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink">
            {["call", "email", "meeting", "note"].map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="What happened?"
          className="min-w-0 flex-1 rounded-lg border border-cardline bg-white px-3 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
        <button type="submit" disabled={log.isPending}
          className="rounded-lg bg-sps-blue px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">Log</button>
      </form>
      <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-muted">Activity stream</h3>
      <div className="mt-2 space-y-2">
        {isLoading ? <Skeleton className="h-20" /> :
          !acts || acts.length === 0 ? <p className="text-sm text-muted">No activity yet.</p> :
          acts.slice().reverse().map((a) => (
            <div key={a.id} className="rounded-lg border border-cardline bg-page px-3 py-2">
              <p className="text-xs font-medium capitalize text-ink">{a.type}</p>
              {a.notes && <p className="text-xs text-ink/80">{a.notes}</p>}
              <p className="text-[11px] text-muted">{new Date(a.occurred_at).toLocaleString()}</p>
            </div>
          ))}
      </div>
    </aside>
  );
}

export default function CrmPage() {
  const { data: leads, isLoading, isError, refetch } = useLeads();
  const createLead = useCreateLead();
  const transition = useLeadTransition();
  const [company, setCompany] = useState("");
  const [contact, setContact] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lostFor, setLostFor] = useState<Lead | null>(null);
  const [convertFor, setConvertFor] = useState<Lead | null>(null);
  const [selected, setSelected] = useState<Lead | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }), useSensor(KeyboardSensor));

  const byStage = (s: string) => (leads ?? []).filter((l) => l.stage === s);

  function move(lead: Lead, to: string, reason?: string) {
    setError(null);
    transition.mutate({ id: lead.id, to_stage: to, reason },
      { onError: (e) => setError(errText(e)) });
  }
  function onDragEnd(e: DragEndEvent) {
    const from = String(e.active.data.current?.stage ?? "");
    const to = e.over ? String(e.over.id) : "";
    if (!to || to === from) return;
    const lead = (leads ?? []).find((l) => l.id === String(e.active.id));
    if (!lead) return;
    if (to === "lost") { setLostFor(lead); return; }   // reason first, then transition
    move(lead, to);
  }

  const handlers = { onOpen: setSelected, onLost: setLostFor, onConvert: setConvertFor };
  return (
    <AppShell role="employee" title="CRM & Leads">
      <SectionCard title="New lead">
        <form className="flex flex-wrap items-end gap-2" noValidate
          onSubmit={(e) => { e.preventDefault(); setError(null);
            createLead.mutate({ company: company.trim(), contact_name: contact.trim() || undefined },
              { onSuccess: () => { setCompany(""); setContact(""); },
                onError: (er) => setError(errText(er)) }); }}>
          <label className="text-xs text-muted">Company
            <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Prospect Co"
              className="mt-1 block w-56 rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
          </label>
          <label className="text-xs text-muted">Contact
            <input value={contact} onChange={(e) => setContact(e.target.value)} placeholder="BD contact name"
              className="mt-1 block w-48 rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
          </label>
          <button type="submit" disabled={company.trim().length < 2 || createLead.isPending}
            className="rounded-lg bg-sps-blue px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            Add lead
          </button>
        </form>
      </SectionCard>

      {error && <p role="alert" className="mt-4 rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">{error}</p>}

      <div className="mt-6">
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
            {[...ACTIVE_COLS, ...TERMINAL_COLS].map((c) => <Skeleton key={c} className="h-28" />)}
          </div>
        ) : isError || !leads ? (
          <p className="text-sm text-muted">Couldn&apos;t load leads.{" "}
            <button onClick={() => refetch()} className="text-[#1B5FE8] underline">Retry</button></p>
        ) : leads.length === 0 ? (
          <EmptyState icon={<ArrowRightCircle size={28} />} title="No leads yet"
            hint="Add a prospect above and work it across the board." />
        ) : (
          <DndContext sensors={sensors} onDragEnd={onDragEnd}>
            <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
              {ACTIVE_COLS.map((s) => (
                <Column key={s} stage={s} leads={byStage(s)} busy={transition.isPending}
                        handlers={handlers} droppable />
              ))}
              {TERMINAL_COLS.map((s) => (
                <Column key={s} stage={s} leads={byStage(s)} busy={transition.isPending}
                        handlers={handlers} droppable />
              ))}
            </div>
          </DndContext>
        )}
      </div>

      {lostFor && <LostModal lead={lostFor} onCancel={() => setLostFor(null)}
        onConfirm={(reason) => { move(lostFor, "lost", reason); setLostFor(null); }} />}
      {convertFor && <ConvertModal lead={convertFor} onClose={() => setConvertFor(null)} />}
      {selected && <LeadPanel lead={selected} onClose={() => setSelected(null)} />}
    </AppShell>
  );
}
