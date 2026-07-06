"use client";
/* Student portal home ("My Academy", FE#4) — lists the student's OWN enrolments
 * from GET /academy/students/me/enrollments, and surfaces an active aptitude test.
 * The take LINK is not returnable by a student endpoint (B.7 one-time token is
 * unstored) — see the note under an active test. */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { GraduationCap, ClipboardCheck, ArrowRight, Download, CheckCircle2 } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { formatFee, realText } from "../../../(marketing)/academy/_lib";

type Enrollment = {
  enrollment_id: string;
  course: { title: string | null; slug: string | null; fee: number | null };
  status: string;
  aptitude_score: number | null;
  discount_percent: number | null;
  final_fee: number | null;
  currency: string;
  payment_status: string;
  has_receipt: boolean;
  active_test: { valid_until: string; attempt_no: number } | null;
};

type ReceiptErr = { id: string; msg: string } | null;

const STATUS_COPY: Record<string, string> = {
  applied: "Applied", tested: "Test complete", offered: "Offer ready",
  active: "Enrolled", completed: "Completed", dropped: "Dropped", cancelled: "Cancelled",
};

function StatusPill({ status }: { status: string }) {
  const gold = ["offered", "tested"].includes(status);
  const green = ["active", "completed"].includes(status);
  const bg = green ? "#F0FDF4" : gold ? "#FFFBEB" : "#EFF6FF";
  const fg = green ? "#16A34A" : gold ? "#B45309" : "#2563EB";
  return (
    <span className="rounded-full px-2.5 py-1 text-xs font-semibold" style={{ background: bg, color: fg }}>
      {STATUS_COPY[status] ?? status}
    </span>
  );
}

// FE#5 — result/discount panel. Shown for a graded enrolment (offered/active/
// completed with a score). <75 earns no discount = FULL PRICE, framed as the
// student's price (NOT a failure or a gate — decision 5). All money is the
// backend's number (course.fee list + final_fee), never recomputed.
const RESULT_STATES = ["offered", "active", "completed"];

function ResultPanel({ e, onDownload, receiptErr }:
  { e: Enrollment; onDownload: (id: string) => void; receiptErr: ReceiptErr }) {
  const score = e.aptitude_score;
  const list = e.course.fee;
  const final = e.final_fee;
  const discount = e.discount_percent ?? 0;
  if (score == null || list == null || final == null) return null;
  const hasDiscount = discount > 0;
  const saved = Math.max(0, list - final);
  return (
    <div className="mt-5 rounded-xl p-5"
      style={{ background: hasDiscount ? "#F0FDF4" : "#F0F4FA", border: `1px solid ${hasDiscount ? "#BBF7D0" : "#EAEEF3"}` }}>
      <p className="text-sm font-semibold" style={{ color: "#0A1628" }}>Your entrance result</p>
      <p className="mt-1 text-sm" style={{ color: "#0A1628" }}>You scored <b>{score}%</b>.</p>
      <p className="mt-0.5 text-sm" style={{ color: hasDiscount ? "#15803D" : "#6B7689" }}>
        {hasDiscount
          ? `Your score earned a ${discount}% discount.`
          : "This programme is at the full fee for your entrance score."}
      </p>
      <div className="mt-4 space-y-1.5 text-sm">
        <div className="flex justify-between" style={{ color: "#6B7689" }}>
          <span>Programme fee</span><span>{formatFee(list, e.currency)}</span>
        </div>
        {hasDiscount && (
          <div className="flex justify-between" style={{ color: "#15803D" }}>
            <span>Discount ({discount}%)</span><span>−{formatFee(saved, e.currency)}</span>
          </div>
        )}
        <div className="mt-1.5 flex justify-between border-t pt-2 text-base font-extrabold"
          style={{ borderColor: "#E5EAF0", color: "#0A1628" }}>
          <span>You pay</span><span>{formatFee(final, e.currency)}</span>
        </div>
      </div>
      {e.payment_status !== "paid" ? (
        <Link href={`/academy/student/pay?enrollment=${e.enrollment_id}`}
          className="mt-4 inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold"
          style={{ background: "#E8A020", color: "#0A1628" }}>
          Proceed to payment <ArrowRight size={15} />
        </Link>
      ) : (
        <div className="mt-4">
          <p className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: "#15803D" }}>
            <CheckCircle2 size={15} /> Paid — you&apos;re enrolled
          </p>
          {/* "Download receipt" ONLY where has_receipt is true — the button's presence
              is truthful; a paid-but-no-receipt row (seed shortcut / Part-D pending
              window) shows NO button. */}
          {e.has_receipt && (
            <button onClick={() => onDownload(e.enrollment_id)}
              className="mt-2 inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold"
              style={{ background: "#F0F4FA", color: "#0A1628" }}>
              <Download size={15} /> Download receipt
            </button>
          )}
          {receiptErr?.id === e.enrollment_id && (
            <p className="mt-2 text-xs" style={{ color: "#B91C1C" }}>{receiptErr.msg}</p>
          )}
        </div>
      )}
    </div>
  );
}

type Notif = { template_code: string; take_link: string | null; created_at: string | null };

export default function StudentHome() {
  const router = useRouter();
  const [rows, setRows] = useState<Enrollment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receiptErr, setReceiptErr] = useState<ReceiptErr>(null);

  async function downloadReceipt(id: string) {
    setReceiptErr(null);
    try {
      // GET the receipt — a FRESH presigned URL each click (5-min TTL never stale).
      const res = await api<{ receipt_url: string }>(`/academy/students/me/enrollments/${id}/receipt`);
      if (res.receipt_url) window.open(res.receipt_url, "_blank", "noopener");
      else setReceiptErr({ id, msg: "Your receipt isn't ready yet — please check back shortly." });
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === "UNAUTHENTICATED") { router.replace("/academy/login"); return; }
        setReceiptErr({ id, msg: e.code === "RECEIPT_NOT_AVAILABLE"
          ? "Your receipt isn't ready yet — please check back shortly."
          : "Couldn't fetch your receipt — please try again." });
      } else {
        setReceiptErr({ id, msg: "Couldn't reach the server — please try again." });
      }
    }
  }
  // the one-time take link lives ONLY in the student's own invite notification
  // (the enrolments endpoint stays presence-only) — pull the latest one here.
  const [takeLink, setTakeLink] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api<Enrollment[]>("/academy/students/me/enrollments")
      .then((d) => { if (alive) setRows(d); })
      .catch((e) => { if (alive) setError(e instanceof ApiError ? e.message : "Something went wrong"); });
    api<Notif[]>("/academy/students/me/notifications")
      .then((ns) => {
        const invite = ns.find((n) => n.template_code === "academy_aptitude_invite" && n.take_link);
        if (alive && invite) setTakeLink(invite.take_link);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  return (
    <div>
      <h1 className="text-3xl font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
        My Academy
      </h1>
      <p className="mt-2 text-sm" style={{ color: "#6B7689" }}>Your programmes, aptitude test, and enrolment status.</p>

      <div className="mt-8">
        {error ? (
          <div className="rounded-2xl bg-white p-8 text-center" style={{ border: "1px solid #EAEEF3" }}>
            <p className="font-semibold" style={{ color: "#0A1628" }}>We couldn&apos;t load your enrolments.</p>
            <p className="mt-1 text-sm" style={{ color: "#6B7689" }}>{error}. Please try again shortly.</p>
          </div>
        ) : rows === null ? (
          <div className="h-40 animate-pulse rounded-2xl" style={{ background: "#E7ECF3" }} />
        ) : rows.length === 0 ? (
          <div className="rounded-2xl bg-white p-12 text-center" style={{ border: "1px solid #EAEEF3" }}>
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl" style={{ background: "#FBEFD7" }}>
              <GraduationCap size={22} style={{ color: "#E8A020" }} />
            </div>
            <p className="font-semibold" style={{ color: "#0A1628" }}>You haven&apos;t enrolled in a programme yet</p>
            <p className="mt-1 text-sm" style={{ color: "#6B7689" }}>Browse the catalogue and apply to get started.</p>
          </div>
        ) : (
          <div className="space-y-5">
            {rows.map((e) => (
              <div key={e.enrollment_id} className="rounded-2xl bg-white p-6" style={{ border: "1px solid #EAEEF3" }}>
                <div>
                  <h3 className="text-lg font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
                    {realText(e.course.title) ?? "Programme"}
                  </h3>
                  <div className="mt-2"><StatusPill status={e.status} /></div>
                </div>

                {RESULT_STATES.includes(e.status) && e.aptitude_score != null &&
                  <ResultPanel e={e} onDownload={downloadReceipt} receiptErr={receiptErr} />}

                {e.active_test ? (
                  <div className="mt-5 rounded-xl p-4" style={{ background: "#FFFBEB", border: "1px solid #FDE68A" }}>
                    <div className="flex items-center gap-2">
                      <ClipboardCheck size={16} style={{ color: "#B45309" }} />
                      <p className="text-sm font-semibold" style={{ color: "#92400E" }}>
                        Your entrance aptitude test is ready
                      </p>
                    </div>
                    <p className="mt-1 text-xs" style={{ color: "#92400E" }}>
                      Valid until {new Date(e.active_test.valid_until).toLocaleString()}.
                    </p>
                    {takeLink && (
                      <Link href={takeLink} className="mt-3 inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold"
                        style={{ background: "#E8A020", color: "#0A1628" }}>
                        Take aptitude test <ArrowRight size={15} />
                      </Link>
                    )}
                  </div>
                ) : e.status === "applied" ? (
                  <p className="mt-4 text-sm" style={{ color: "#9AA6BC" }}>No aptitude test assigned yet.</p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
