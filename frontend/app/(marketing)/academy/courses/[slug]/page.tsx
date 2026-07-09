"use client";
/* Public academy storefront — course detail (/academy/courses/{slug}). Renders the
 * course's real fields; null/placeholder fields fall back to neutral copy. APPLY
 * routes to surface #2 (student register) — that route 404s until #2 is built. */
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Clock, BarChart3, CalendarDays, Loader2, CheckCircle2 } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { StorefrontShell, formatFee, realText, durationLabel, type PublicCourse } from "../../_lib";

const GOLD = "#E8A020";

type Cohort = { cohort_id: string; name: string; start_date: string | null; mode: string; status: string };
type CohortsResp = { course_id: string; cohorts: Cohort[] };

/** The apply seam. Session-aware: a logged-out visitor gets "Apply now" → register
 *  carrying the course intent as ?next (survives register→login→back); a logged-in
 *  student gets the cohort picker + Apply → dashboard. Apply needs course_id, which
 *  the public cohorts read carries. */
function ApplyPanel({ slug }: { slug: string }) {
  const router = useRouter();
  const [authed, setAuthed] = useState<boolean | null>(null);   // null = checking
  const [data, setData] = useState<CohortsResp | null>(null);
  const [picked, setPicked] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState<"idle" | "already" | "error">("idle");
  const [msg, setMsg] = useState<string | null>(null);
  const inFlight = useRef(false);

  useEffect(() => {
    let alive = true;
    api("/academy/auth/me")
      .then(() => { if (alive) { setAuthed(true); return api<CohortsResp>(`/academy/public/courses/${slug}/cohorts`).then((d) => alive && setData(d)); } })
      .catch((e) => { if (alive && e instanceof ApiError && e.code === "UNAUTHENTICATED") setAuthed(false); else if (alive) setAuthed(false); });
    return () => { alive = false; };
  }, [slug]);

  async function apply() {
    if (inFlight.current || !picked || !data) return;   // in-flight guard: one POST per click
    inFlight.current = true; setBusy(true); setMsg(null);
    try {
      await api("/academy/students/me/enrollments", { method: "POST", body: JSON.stringify({ course_id: data.course_id, cohort_id: picked }) });
      router.push("/academy/student");                  // 201 → the new 'applied' enrolment shows on the dashboard
    } catch (e) {
      inFlight.current = false; setBusy(false);
      if (e instanceof ApiError && e.code === "ALREADY_APPLIED") { setState("already"); return; }
      setState("error"); setMsg(e instanceof ApiError ? e.message : "Couldn't apply. Please try again.");
    }
  }

  const btn = "mt-6 flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold";
  const nextUrl = `/academy/courses/${slug}?apply=1`;

  if (authed === null) {
    return <div className={btn} style={{ background: "#F3F4F6", color: "#9AA6BC" }}><Loader2 size={16} className="animate-spin" /> Loading…</div>;
  }
  if (!authed) {
    return (
      <Link href={`/academy/register?course=${slug}&next=${encodeURIComponent(nextUrl)}`}
        className={btn} style={{ background: GOLD, color: "#0A1628" }}>
        Apply now <ArrowRight size={16} />
      </Link>
    );
  }
  if (state === "already") {
    return (
      <div className="mt-6 rounded-xl px-4 py-3 text-sm" style={{ background: "#F0FDF4", color: "#15803D", border: "1px solid #BBF7D0" }}>
        <p className="flex items-center gap-1.5 font-semibold"><CheckCircle2 size={15} /> You&apos;ve already applied to this course.</p>
        <Link href="/academy/student" className="mt-1 inline-block font-semibold underline">Go to your dashboard →</Link>
      </div>
    );
  }
  const cohorts = data?.cohorts ?? [];
  return (
    <div className="mt-6">
      {cohorts.length === 0 ? (
        <p className="rounded-xl px-4 py-3 text-sm" style={{ background: "#F8FAFC", color: "#6B7689", border: "1px solid #EAEEF3" }}>
          No open cohorts for this course right now. Please check back soon.
        </p>
      ) : (
        <>
          <p className="mb-2 text-sm font-semibold" style={{ color: "#0A1628" }}>Choose a cohort</p>
          <div className="space-y-2">
            {cohorts.map((co) => (
              <label key={co.cohort_id}
                className="flex cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-2.5"
                style={{ borderColor: picked === co.cohort_id ? GOLD : "#DDE3EC", background: picked === co.cohort_id ? "#FFFBEB" : "#fff" }}>
                <input type="radio" name="cohort" className="accent-[#E8A020]" checked={picked === co.cohort_id} onChange={() => setPicked(co.cohort_id)} />
                <span className="text-sm">
                  <span className="font-semibold" style={{ color: "#0A1628" }}>{co.name}</span>
                  <span style={{ color: "#6B7689" }}>{co.start_date ? ` · starts ${new Date(co.start_date).toLocaleDateString()}` : ""} · {co.mode}</span>
                </span>
              </label>
            ))}
          </div>
          {msg && <p className="mt-2 text-xs" style={{ color: "#B91C1C" }}>{msg}</p>}
          <button onClick={apply} disabled={!picked || busy}
            className={btn.replace("mt-6", "mt-4") + " disabled:opacity-50"} style={{ background: GOLD, color: "#0A1628" }}>
            {busy ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
            {busy ? "Applying…" : "Apply"}
          </button>
        </>
      )}
    </div>
  );
}

export default function CourseDetail() {
  const { slug } = useParams<{ slug: string }>();
  const [course, setCourse] = useState<PublicCourse | null>(null);
  const [error, setError] = useState<{ notFound: boolean; msg: string } | null>(null);

  useEffect(() => {
    let alive = true;
    api<PublicCourse>(`/academy/public/courses/${slug}`)
      .then((d) => { if (alive) setCourse(d); })
      .catch((e) => {
        if (!alive) return;
        const notFound = e instanceof ApiError && (e.code === "NOT_FOUND" || /not found/i.test(e.message));
        setError({ notFound, msg: e instanceof ApiError ? e.message : "Something went wrong" });
      });
    return () => { alive = false; };
  }, [slug]);

  const back = (
    <Link href="/academy" className="mb-6 inline-flex items-center gap-1.5 text-xs font-semibold hover:opacity-70"
      style={{ color: "#F6C667" }}>← All courses</Link>
  );

  if (error) {
    return (
      <StorefrontShell title={error.notFound ? "Course not found" : "Something went wrong"} back={back}>
        <div className="rounded-2xl bg-white p-10 text-center" style={{ border: "1px solid #EAEEF3" }}>
          <p className="text-sm" style={{ color: "#6B7689" }}>
            {error.notFound
              ? "This course isn't available. It may have been unpublished."
              : `${error.msg}. Please try again shortly.`}
          </p>
          <Link href="/academy" className="mt-5 inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold"
            style={{ background: GOLD, color: "#0A1628" }}>Browse all courses</Link>
        </div>
      </StorefrontShell>
    );
  }

  if (course === null) {
    return (
      <StorefrontShell title="Loading…" back={back}>
        <div className="h-72 animate-pulse rounded-2xl" style={{ background: "#E7ECF3" }} />
      </StorefrontShell>
    );
  }

  const description = realText(course.description);
  const syllabus = realText(course.syllabus);
  const level = realText(course.level);
  const dur = durationLabel(course.duration_weeks);
  const start = course.next_cohort_start;

  const meta = [
    dur && { icon: Clock, label: "Duration", value: dur },
    level && { icon: BarChart3, label: "Level", value: level },
    start && { icon: CalendarDays, label: "Next cohort", value: start },
  ].filter(Boolean) as { icon: typeof Clock; label: string; value: string }[];

  return (
    <StorefrontShell eyebrow="Training & Internships" title={course.title} back={back}>
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="rounded-2xl bg-white p-8" style={{ border: "1px solid #EAEEF3" }}>
            <h2 className="mb-3 text-lg font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>About this programme</h2>
            <p className="text-sm leading-relaxed" style={{ color: "#5A6B8A" }}>
              {description ?? "A detailed overview of this programme is coming soon."}
            </p>

            <h2 className="mb-3 mt-8 text-lg font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>Syllabus</h2>
            <p className="whitespace-pre-line text-sm leading-relaxed" style={{ color: "#5A6B8A" }}>
              {syllabus ?? "The full syllabus will be published shortly."}
            </p>
          </div>
        </div>

        <aside className="lg:col-span-1">
          <div className="sticky top-24 rounded-2xl bg-white p-7" style={{ border: "1px solid #EAEEF3" }}>
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "#6B7689" }}>Programme fee</p>
            <p className="mt-1 text-3xl font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
              {formatFee(course.fee, course.currency)}
            </p>
            {meta.length > 0 && (
              <ul className="mt-5 space-y-3">
                {meta.map(({ icon: Icon, label, value }) => (
                  <li key={label} className="flex items-center gap-3 text-sm">
                    <Icon size={16} style={{ color: GOLD }} />
                    <span style={{ color: "#6B7689" }}>{label}:</span>
                    <span className="font-semibold" style={{ color: "#0A1628" }}>{value}</span>
                  </li>
                ))}
              </ul>
            )}
            <ApplyPanel slug={course.slug} />
          </div>
        </aside>
      </div>
    </StorefrontShell>
  );
}
