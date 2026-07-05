"use client";
/* Student portal home ("My Academy", FE#4) — lists the student's OWN enrolments
 * from GET /academy/students/me/enrollments, and surfaces an active aptitude test.
 * The take LINK is not returnable by a student endpoint (B.7 one-time token is
 * unstored) — see the note under an active test. */
import { useEffect, useState } from "react";
import { GraduationCap, ClipboardCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { formatFee, realText } from "../../../(marketing)/academy/_lib";

type Enrollment = {
  enrollment_id: string;
  course: { title: string | null; slug: string | null };
  status: string;
  aptitude_score: number | null;
  discount_percent: number | null;
  final_fee: number | null;
  currency: string;
  payment_status: string;
  active_test: { valid_until: string; attempt_no: number } | null;
};

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

export default function StudentHome() {
  const [rows, setRows] = useState<Enrollment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api<Enrollment[]>("/academy/students/me/enrollments")
      .then((d) => { if (alive) setRows(d); })
      .catch((e) => { if (alive) setError(e instanceof ApiError ? e.message : "Something went wrong"); });
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
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
                      {realText(e.course.title) ?? "Programme"}
                    </h3>
                    <div className="mt-2"><StatusPill status={e.status} /></div>
                  </div>
                  {e.final_fee != null && (
                    <div className="text-right">
                      <p className="text-xs" style={{ color: "#9AA6BC" }}>Your fee</p>
                      <p className="text-lg font-extrabold" style={{ color: "#0A1628" }}>{formatFee(e.final_fee, e.currency)}</p>
                    </div>
                  )}
                </div>

                {(e.aptitude_score != null || e.discount_percent != null) && (
                  <div className="mt-4 flex gap-6 text-sm" style={{ color: "#6B7689" }}>
                    {e.aptitude_score != null && <span>Aptitude score: <b style={{ color: "#0A1628" }}>{e.aptitude_score}%</b></span>}
                    {e.discount_percent != null && <span>Discount earned: <b style={{ color: "#0A1628" }}>{e.discount_percent}%</b></span>}
                  </div>
                )}

                {e.active_test ? (
                  <div className="mt-5 rounded-xl p-4" style={{ background: "#FFFBEB", border: "1px solid #FDE68A" }}>
                    <div className="flex items-center gap-2">
                      <ClipboardCheck size={16} style={{ color: "#B45309" }} />
                      <p className="text-sm font-semibold" style={{ color: "#92400E" }}>
                        Your entrance aptitude test is ready
                      </p>
                    </div>
                    <p className="mt-1 text-xs" style={{ color: "#92400E" }}>
                      Valid until {new Date(e.active_test.valid_until).toLocaleString()}. Open the test using the
                      link from your invitation to begin.
                    </p>
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
