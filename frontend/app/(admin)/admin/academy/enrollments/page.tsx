"use client";
/* FE#8a — STAFF academy roster (admin area, staff access_token-gated via /admin/*
 * middleware). READ-ONLY: no mutation controls (issue/status-move/waive = 8b).
 * Cross-student roster onto GET /academy/enrollments; unmasked staff identity. */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { api, ApiError } from "@/lib/api/client";
import { BookOpen } from "lucide-react";

type Row = {
  enrollment_id: string;
  status: string;
  aptitude_score: number | null;
  discount_percent: number | null;
  final_fee: number | null;
  currency: string;
  payment_status: string;
  has_receipt: boolean;
  course: { id: string; title: string | null; slug: string | null } | null;
  cohort: { id: string; name: string | null } | null;
  student: { id: string; full_name: string; email: string | null; college_student_id: string | null; college_name: string | null } | null;
};
type Course = { id: string; title: string };
type Cohort = { id: string; name: string };

const STATUSES = ["applied", "tested", "offered", "active", "completed", "dropped", "cancelled"];
const fmtFee = (n: number | null, c: string) =>
  n == null ? "—" : new Intl.NumberFormat("en-IN", { style: "currency", currency: c, maximumFractionDigits: 0 }).format(n);

export default function AcademyRoster() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [status, setStatus] = useState("");
  const [courseId, setCourseId] = useState("");
  const [cohortId, setCohortId] = useState("");

  // staff 401 → the STAFF session expired (route to staff login, not the academy login)
  function onErr(e: unknown) {
    if (e instanceof ApiError && e.code === "UNAUTHENTICATED") { router.replace("/login?role=admin"); return; }
    setError(e instanceof ApiError ? e.message : "Something went wrong");
  }

  useEffect(() => {
    api<Course[]>("/academy/courses").then((c) => setCourses(c.map((x) => ({ id: x.id, title: x.title })))).catch(() => {});
  }, []);

  useEffect(() => {
    if (!courseId) { setCohorts([]); return; }
    api<Cohort[]>(`/academy/courses/${courseId}/cohorts`).then((c) => setCohorts(c.map((x) => ({ id: x.id, name: x.name })))).catch(() => setCohorts([]));
  }, [courseId]);

  useEffect(() => {
    let alive = true;
    setRows(null); setError(null);
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    if (courseId) q.set("course_id", courseId);
    if (cohortId) q.set("cohort_id", cohortId);
    api<Row[]>(`/academy/enrollments${q.toString() ? `?${q}` : ""}`)
      .then((d) => { if (alive) setRows(d); })
      .catch((e) => { if (alive) onErr(e); });
    return () => { alive = false; };
  }, [status, courseId, cohortId]);

  const selCls = "rounded-lg border border-cardline bg-card px-2.5 py-1.5 text-sm text-ink";

  return (
    <AppShell role="admin" title="Academy — Roster">
      <SectionCard title="Enrolments" actions={
        <div className="flex flex-wrap gap-2">
          <select className={selCls} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className={selCls} value={courseId} onChange={(e) => { setCourseId(e.target.value); setCohortId(""); }}>
            <option value="">All courses</option>
            {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
          <select className={selCls} value={cohortId} onChange={(e) => setCohortId(e.target.value)} disabled={!courseId}>
            <option value="">All cohorts</option>
            {cohorts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
      }>
        {error ? (
          <p className="py-6 text-sm text-[#DC2626]">{error}. Please try again.</p>
        ) : rows === null ? (
          <div className="space-y-2 py-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-9 w-full" />)}</div>
        ) : rows.length === 0 ? (
          <EmptyState icon={<BookOpen size={28} />} title="No enrolments"
            hint="Academy enrolments matching these filters will appear here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-cardline text-xs uppercase tracking-wide text-muted">
                  <th className="py-2 pr-3">Student</th><th className="py-2 pr-3">Course</th>
                  <th className="py-2 pr-3">Cohort</th><th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Score</th><th className="py-2 pr-3">Discount</th>
                  <th className="py-2 pr-3">Fee</th><th className="py-2">Payment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cardline">
                {rows.map((r) => (
                  <tr key={r.enrollment_id} className="cursor-pointer hover:bg-page">
                    <td className="py-2 pr-3">
                      <Link href={`/admin/academy/enrollments/${r.enrollment_id}`} className="block">
                        <span className="font-semibold text-ink">{r.student?.full_name ?? "—"}</span>
                        <span className="block text-xs text-muted">{r.student?.email ?? ""}</span>
                      </Link>
                    </td>
                    <td className="py-2 pr-3 text-muted">{r.course?.title ?? "—"}</td>
                    <td className="py-2 pr-3 text-muted">{r.cohort?.name ?? "—"}</td>
                    <td className="py-2 pr-3"><StatusPill status={r.status} /></td>
                    <td className="py-2 pr-3 text-muted">{r.aptitude_score != null ? `${r.aptitude_score}%` : "—"}</td>
                    <td className="py-2 pr-3 text-muted">{r.discount_percent != null ? `${r.discount_percent}%` : "—"}</td>
                    <td className="py-2 pr-3 text-ink">{fmtFee(r.final_fee, r.currency)}</td>
                    <td className="py-2"><StatusPill status={r.payment_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </AppShell>
  );
}
