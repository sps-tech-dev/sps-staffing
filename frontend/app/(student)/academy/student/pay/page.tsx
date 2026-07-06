"use client";
/* Student pay confirmation (FE#6) — onto POST /academy/students/me/enrollments/{id}/pay
 * (the A6 STUB: marks paid, no real money; Razorpay = Part-D). The risk is the
 * frontend's handling of a state-changing call: the in-flight guard (exactly one
 * POST on double-click) and the network-unknown case (reconcile from server truth,
 * never assume failure) are the point. Receipt link is fetched fresh per download
 * (the pay response's presigned URL is ~5-min TTL). */
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, Loader2, AlertTriangle, Download, ArrowLeft, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { formatFee, realText } from "../../../../(marketing)/academy/_lib";

const GOLD = "#E8A020";
const PAID = ["active", "completed"];

type Enrollment = {
  enrollment_id: string;
  course: { title: string | null; slug: string | null; fee: number | null };
  status: string;
  final_fee: number | null;
  currency: string;
  payment_status: string;
};
type PayResult = { status: string; enrollment_status: string; receipt_url: string | null };

type Phase = "loading" | "offered" | "paying" | "confirming" | "done" | "notdue" | "conflict" | "unconfirmed";

function isEnrolled(e: Enrollment | null) {
  return !!e && (PAID.includes(e.status) || e.payment_status === "paid");
}

function PayInner() {
  const router = useRouter();
  const enrollmentId = useSearchParams().get("enrollment");
  const [enr, setEnr] = useState<Enrollment | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [msg, setMsg] = useState<string | null>(null);
  const inFlight = useRef(false);        // IN-FLIGHT GUARD — survives re-render, checked synchronously

  const path = `/academy/students/me/enrollments/${enrollmentId}/pay`;

  async function fetchEnr(): Promise<Enrollment | null> {
    const rows = await api<Enrollment[]>("/academy/students/me/enrollments");
    return rows.find((r) => r.enrollment_id === enrollmentId) ?? null;
  }

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const e = await fetchEnr();
        if (!alive) return;
        if (!e) { setPhase("conflict"); setMsg("We couldn't find this enrolment."); return; }
        setEnr(e);
        setPhase(isEnrolled(e) ? "done" : e.status === "offered" ? "offered" : "notdue");
      } catch (err) {
        if (!alive) return;
        if (err instanceof ApiError && err.code === "UNAUTHENTICATED") { router.replace("/academy/login"); return; }
        setPhase("conflict"); setMsg("We couldn't load this enrolment. Please try again.");
      }
    })();
    return () => { alive = false; };
  }, [enrollmentId]);

  async function pay() {
    if (inFlight.current) return;        // ← a double/impatient click returns here: NO second POST
    inFlight.current = true;
    setPhase("paying"); setMsg(null);
    try {
      const res = await api<PayResult>(path, { method: "POST" });
      setEnr((p) => (p ? { ...p, status: "active", payment_status: "paid" } : p));
      setPhase("done");
      void res;                          // receipt is fetched fresh on download (TTL), not stored
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "UNAUTHENTICATED") { router.replace("/academy/login"); return; }
        if (err.code === "STATUS_INVALID") {
          // maybe it already activated — reconcile before calling it a conflict
          const fresh = await fetchEnr().catch(() => null);
          if (isEnrolled(fresh)) { setEnr(fresh); setPhase("done"); }
          else { setEnr(fresh ?? enr); setMsg("This enrolment isn't awaiting payment."); setPhase("conflict"); }
        } else {
          setMsg(err.message); setPhase("conflict");
        }
      } else {
        // NETWORK error — outcome UNKNOWN. Do NOT say "failed", do NOT retry-fire.
        // Reconcile against server truth.
        setPhase("confirming");
        const fresh = await fetchEnr().catch(() => null);
        if (isEnrolled(fresh)) { setEnr(fresh); setPhase("done"); }
        else {
          setEnr(fresh ?? enr);
          setMsg("We couldn't confirm your payment just now. If you may have been charged, do NOT pay again — refresh in a moment.");
          setPhase("unconfirmed");
        }
      }
    } finally {
      inFlight.current = false;
    }
  }

  async function downloadReceipt() {
    // POST /pay is idempotent (no-op when already paid) and returns a FRESH presigned
    // receipt URL each call — this is how the ~5-min TTL is handled (fetch-on-click).
    try {
      const res = await api<PayResult>(path, { method: "POST" });
      if (res.receipt_url) window.open(res.receipt_url, "_blank", "noopener");
      else setMsg("Receipt isn't available yet — please try again shortly.");
    } catch {
      setMsg("Couldn't fetch your receipt just now — please try again.");
    }
  }

  const back = (
    <Link href="/academy/student" className="mb-6 inline-flex items-center gap-1.5 text-sm font-semibold" style={{ color: GOLD }}>
      <ArrowLeft size={15} /> My Academy
    </Link>
  );
  const course = enr ? realText(enr.course.title) ?? "Programme" : "";
  const stubNote = (
    <p className="mt-4 flex items-center justify-center gap-1.5 text-center text-xs" style={{ color: "#9AA6BC" }}>
      <ShieldCheck size={12} /> Dev/stub payment — no real money is charged (gateway integration is Part-D).
    </p>
  );

  if (phase === "loading") {
    return <Shell back={back}><div className="h-40 animate-pulse rounded-2xl" style={{ background: "#E7ECF3" }} /></Shell>;
  }

  if (phase === "done") {
    return (
      <Shell back={back}>
        <div className="mx-auto max-w-lg rounded-2xl bg-white p-8 text-center" style={{ border: "1px solid #EAEEF3" }}>
          <CheckCircle2 size={40} className="mx-auto mb-4" style={{ color: "#16A34A" }} />
          <p className="text-lg font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>You&apos;re enrolled</p>
          <p className="mt-1 text-sm" style={{ color: "#6B7689" }}>Your payment for {course} is confirmed.</p>
          <button onClick={downloadReceipt} className="mt-6 inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold"
            style={{ background: "#F0F4FA", color: "#0A1628" }}>
            <Download size={15} /> Download receipt
          </button>
          {msg && <p className="mt-3 text-xs" style={{ color: "#B91C1C" }}>{msg}</p>}
          <div className="mt-5"><Link href="/academy/student" className="text-sm font-semibold" style={{ color: GOLD }}>Back to My Academy →</Link></div>
        </div>
      </Shell>
    );
  }

  if (phase === "notdue") {
    return (
      <Shell back={back}>
        <div className="mx-auto max-w-lg rounded-2xl bg-white p-8 text-center" style={{ border: "1px solid #EAEEF3" }}>
          <p className="font-semibold" style={{ color: "#0A1628" }}>Nothing due yet</p>
          <p className="mt-1 text-sm" style={{ color: "#6B7689" }}>
            This enrolment isn&apos;t awaiting payment. Complete your entrance test first, and your offer will appear on My Academy.
          </p>
        </div>
      </Shell>
    );
  }

  if (phase === "conflict") {
    return (
      <Shell back={back}>
        <div className="mx-auto max-w-lg rounded-2xl bg-white p-8 text-center" style={{ border: "1px solid #FECACA" }}>
          <AlertTriangle size={28} className="mx-auto mb-3" style={{ color: "#B45309" }} />
          <p className="font-semibold" style={{ color: "#0A1628" }}>{msg ?? "We couldn't process this."}</p>
          <div className="mt-5"><Link href="/academy/student" className="text-sm font-semibold" style={{ color: GOLD }}>Back to My Academy →</Link></div>
        </div>
      </Shell>
    );
  }

  if (phase === "unconfirmed") {
    return (
      <Shell back={back}>
        <div className="mx-auto max-w-lg rounded-2xl bg-white p-8 text-center" style={{ border: "1px solid #FDE68A", background: "#FFFBEB" }}>
          <AlertTriangle size={28} className="mx-auto mb-3" style={{ color: "#B45309" }} />
          <p className="font-semibold" style={{ color: "#92400E" }}>{msg}</p>
          <button onClick={() => { setPhase("loading"); window.location.reload(); }}
            className="mt-5 inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold" style={{ background: GOLD, color: "#0A1628" }}>
            Check again
          </button>
        </div>
      </Shell>
    );
  }

  // phase === "offered" | "paying" — the confirmation screen
  const busy = phase === "paying" || phase === "confirming";
  return (
    <Shell back={back}>
      <div className="mx-auto max-w-lg rounded-2xl bg-white p-8" style={{ border: "1px solid #EAEEF3" }}>
        <h2 className="text-xl font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Confirm & pay</h2>
        <div className="mt-5 space-y-2 rounded-xl p-4" style={{ background: "#F0F4FA" }}>
          <div className="flex justify-between text-sm"><span style={{ color: "#6B7689" }}>Programme</span><span className="font-semibold" style={{ color: "#0A1628" }}>{course}</span></div>
          <div className="flex justify-between border-t pt-2 text-base font-extrabold" style={{ borderColor: "#E5EAF0", color: "#0A1628" }}>
            <span>Amount due</span><span>{enr?.final_fee != null ? formatFee(enr.final_fee, enr.currency) : "—"}</span>
          </div>
        </div>
        <button onClick={pay} disabled={busy}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold disabled:opacity-60"
          style={{ background: GOLD, color: "#0A1628" }}>
          {busy && <Loader2 size={16} className="animate-spin" />}
          {phase === "confirming" ? "Confirming your payment…" : busy ? "Processing…" : "Pay & enrol"}
        </button>
        {stubNote}
      </div>
    </Shell>
  );
}

function Shell({ children, back }: { children: React.ReactNode; back: React.ReactNode }) {
  return (
    <div>
      <div>{back}</div>
      {children}
    </div>
  );
}

export default function PayPage() {
  return (
    <Suspense fallback={<div className="h-40 animate-pulse rounded-2xl" style={{ background: "#E7ECF3" }} />}>
      <PayInner />
    </Suspense>
  );
}
