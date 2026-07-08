"use client";
/* FE#8a — STAFF enrolment detail (admin, read-only). Full unmasked student +
 * pricing/payment + test/score. NO mutation controls (issue/status-move/waive are
 * 8b, gated on the transition-machine STOP-0) — an intentionally empty actions slot,
 * not a stub. */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { api, ApiError } from "@/lib/api/client";
import { ArrowLeft } from "lucide-react";

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

export default function EnrolmentDetail() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState<{ notFound: boolean; msg: string } | null>(null);

  useEffect(() => {
    let alive = true;
    api<Detail>(`/academy/enrollments/${id}`)
      .then((x) => { if (alive) setD(x); })
      .catch((e) => {
        if (!alive) return;
        if (e instanceof ApiError && e.code === "UNAUTHENTICATED") { router.replace("/login?role=admin"); return; }
        setErr({ notFound: e instanceof ApiError && e.code === "NOT_FOUND", msg: e instanceof ApiError ? e.message : "Something went wrong" });
      });
    return () => { alive = false; };
  }, [id, router]);

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
            {/* Actions (issue test / status move / waive) arrive in 8b — intentionally empty, not stubbed. */}
          </div>
        </div>
      )}
    </AppShell>
  );
}
