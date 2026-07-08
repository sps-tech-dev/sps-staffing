"use client";
/* FE#8a detail + 8b STAFF action controls. The actions slot renders ONLY the moves
 * the 8b-1 machine permits FROM the enrolment's current status (the frontend mirror
 * of the transition table) — never a control the backend would 409. NO "activate"
 * control ever: 'active' is reached only by pay/waive, never a manual move. */
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { api, ApiError } from "@/lib/api/client";
import { ArrowLeft } from "lucide-react";

// The frontend mirror of the 8b-1 transition table: the legal MANUAL moves from
// each status. Terminal states (cancelled/dropped/completed) → no controls. A
// 'waive' is 8b-3 (offered only). NO entry produces 'active' — never a manual move.
type Action =
  | { kind: "waive"; label: string; title: string; danger?: boolean }
  | { kind: "status"; to_state: string; label: string; title: string; danger?: boolean };

function actionsFor(status: string): Action[] {
  switch (status) {
    case "offered":
      return [
        { kind: "waive", label: "Waive fee", title: "Waive the fee (enrol without payment)" },
        { kind: "status", to_state: "cancelled", label: "Cancel", title: "Cancel this enrolment", danger: true },
      ];
    case "applied":
    case "tested":
      return [{ kind: "status", to_state: "cancelled", label: "Cancel", title: "Cancel this enrolment", danger: true }];
    case "active":
      return [
        { kind: "status", to_state: "completed", label: "Mark completed", title: "Mark this enrolment completed" },
        { kind: "status", to_state: "dropped", label: "Mark dropped", title: "Mark this enrolment dropped", danger: true },
      ];
    default:
      return []; // terminal — nothing legal
  }
}

type Detail = {
  enrollment_id: string;
  status: string;
  aptitude_score: number | null;
  discount_percent: number | null;
  final_fee: number | null;
  currency: string;
  payment_status: string;
  has_receipt: boolean;
  course: { title: string | null; slug: string | null } | null;
  cohort: { name: string | null } | null;
  student: {
    full_name: string; email: string | null; college_student_id: string | null;
    college_name: string | null; course_degree?: string | null; year_of_study?: string | null;
    date_of_birth?: string | null;
  } | null;
  payment: { status: string; amount: number; currency: string; paid_at: string | null; provider: string } | null;
  test: { attempt_no: number; status: string; score: number | null; submitted_at: string | null; valid_until: string | null } | null;
};

const fmtFee = (n: number | null | undefined, c: string) =>
  n == null ? "—" : new Intl.NumberFormat("en-IN", { style: "currency", currency: c, maximumFractionDigits: 0 }).format(n);

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 text-sm text-ink">{value ?? "—"}</p>
    </div>
  );
}

/** Action confirm — reason is REQUIRED (both endpoints 422 without one); submit is
 *  disabled until reason is non-empty (mirrors the backend). In-flight guard: a
 *  synchronous ref gate + disabled button → exactly one request per confirm. */
function ActionModal({ enrollmentId, action, onCancel, onDone }:
  { enrollmentId: string; action: Action; onCancel: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const inFlight = useRef(false);

  async function submit() {
    if (inFlight.current || !reason.trim()) return;   // synchronous double-fire guard
    inFlight.current = true; setBusy(true); setErr(null);
    try {
      if (action.kind === "waive") {
        await api(`/academy/enrollments/${enrollmentId}/waive`, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) });
      } else {
        await api(`/academy/enrollments/${enrollmentId}/status`, { method: "POST", body: JSON.stringify({ to_state: action.to_state, reason: reason.trim() }) });
      }
      onDone();                                        // success → parent refreshes the detail
    } catch (e) {
      // the machine's 409 (a race — status changed under us) or any error: show it +
      // refresh so a now-illegal control doesn't linger.
      setErr(e instanceof ApiError ? e.message : "Couldn't complete the action.");
      inFlight.current = false; setBusy(false);
      if (e instanceof ApiError && e.code === "ILLEGAL_TRANSITION") onDone();
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-sm rounded-2xl border border-cardline bg-card p-5 shadow-lg">
        <h3 className="font-display text-base font-bold text-ink">{action.title} — reason required</h3>
        <p className="mt-1 text-xs text-muted">This is recorded against the enrolment and attributed to you.</p>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} autoFocus
          placeholder="Reason (required)"
          className="mt-3 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
        {err && <p role="alert" className="mt-2 text-xs text-[#DC2626]">{err}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} disabled={busy} className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-page disabled:opacity-40">Cancel</button>
          <button disabled={!reason.trim() || busy} onClick={submit}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40 ${action.danger ? "bg-[#DC2626]" : "bg-[#1B5FE8]"}`}>
            {busy ? "Working…" : `Confirm — ${action.label}`}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function EnrolmentDetail() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState<{ notFound: boolean; msg: string } | null>(null);
  const [action, setAction] = useState<Action | null>(null);

  const load = useCallback(() => {
    api<Detail>(`/academy/enrollments/${id}`)
      .then(setD)
      .catch((e) => {
        if (e instanceof ApiError && e.code === "UNAUTHENTICATED") { router.replace("/login?role=admin"); return; }
        setErr({ notFound: e instanceof ApiError && e.code === "NOT_FOUND", msg: e instanceof ApiError ? e.message : "Something went wrong" });
      });
  }, [id, router]);

  useEffect(() => { load(); }, [load]);

  const back = (
    <Link href="/admin/academy/enrollments" className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-sps-blue">
      <ArrowLeft size={15} /> Roster
    </Link>
  );

  return (
    <AppShell role="admin" title="Academy — Enrolment">
      {back}
      {err ? (
        <SectionCard title={err.notFound ? "Enrolment not found" : "Couldn't load"}>
          <p className="py-4 text-sm text-muted">
            {err.notFound ? "This enrolment isn't in your tenant." : `${err.msg}. Please try again.`}
          </p>
        </SectionCard>
      ) : d === null ? (
        <SectionCard title="Enrolment"><div className="space-y-2 py-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-8 w-full" />)}</div></SectionCard>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-5">
            <SectionCard title="Student">
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <Field label="Name" value={d.student?.full_name} />
                <Field label="Email" value={d.student?.email} />
                <Field label="College ID" value={d.student?.college_student_id} />
                <Field label="College" value={d.student?.college_name} />
                <Field label="Degree" value={d.student?.course_degree} />
                <Field label="Year" value={d.student?.year_of_study} />
                <Field label="Date of birth" value={d.student?.date_of_birth} />
              </div>
            </SectionCard>
            <SectionCard title="Aptitude test">
              {d.test ? (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <Field label="Attempt" value={`#${d.test.attempt_no}`} />
                  <Field label="Status" value={<StatusPill status={d.test.status} />} />
                  <Field label="Score" value={d.test.score != null ? `${(d.test.score * 100).toFixed(0)}%` : "—"} />
                  <Field label="Submitted" value={d.test.submitted_at ? new Date(d.test.submitted_at).toLocaleString() : "—"} />
                </div>
              ) : <p className="py-2 text-sm text-muted">No aptitude test issued.</p>}
            </SectionCard>
          </div>
          <div className="space-y-5">
            <SectionCard title="Enrolment">
              <div className="space-y-3">
                <Field label="Programme" value={d.course?.title} />
                <Field label="Cohort" value={d.cohort?.name} />
                <Field label="Status" value={<StatusPill status={d.status} />} />
                <Field label="Aptitude score" value={d.aptitude_score != null ? `${d.aptitude_score}%` : "—"} />
                <Field label="Discount" value={d.discount_percent != null ? `${d.discount_percent}%` : "—"} />
                <Field label="Final fee" value={fmtFee(d.final_fee, d.currency)} />
              </div>
            </SectionCard>
            <SectionCard title="Payment">
              <div className="space-y-3">
                <Field label="Payment status" value={<StatusPill status={d.payment_status} />} />
                {d.payment ? (
                  <>
                    <Field label="Amount" value={fmtFee(d.payment.amount, d.payment.currency)} />
                    <Field label="Paid at" value={d.payment.paid_at ? new Date(d.payment.paid_at).toLocaleString() : "—"} />
                    <Field label="Provider" value={d.payment.provider} />
                  </>
                ) : <p className="text-sm text-muted">No payment yet.</p>}
              </div>
            </SectionCard>
            {/* 8b action controls — ONLY the moves legal from d.status (machine mirror). */}
            {(() => {
              const acts = actionsFor(d.status);
              return (
                <SectionCard title="Actions">
                  {acts.length === 0 ? (
                    <p className="py-1 text-sm text-muted">
                      This enrolment is {d.status} — no further actions.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {acts.map((a) => (
                        <button key={a.label} onClick={() => setAction(a)} title={a.title}
                          className={`rounded-xl px-4 py-2 text-sm font-semibold ${a.danger
                            ? "border border-[#DC2626] text-[#DC2626] hover:bg-[#FEF2F2]"
                            : "border border-cardline text-ink hover:bg-page"}`}>
                          {a.label}
                        </button>
                      ))}
                    </div>
                  )}
                </SectionCard>
              );
            })()}
          </div>
        </div>
      )}
      {d !== null && action !== null && (
        <ActionModal enrollmentId={d.enrollment_id} action={action}
          onCancel={() => setAction(null)}
          onDone={() => { setAction(null); setD(null); load(); }} />
      )}
    </AppShell>
  );
}
