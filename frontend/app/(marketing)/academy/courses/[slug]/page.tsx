"use client";
/* Public academy storefront — course detail (/academy/courses/{slug}). Renders the
 * course's real fields; null/placeholder fields fall back to neutral copy. APPLY
 * routes to surface #2 (student register) — that route 404s until #2 is built. */
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Clock, BarChart3, CalendarDays } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { StorefrontShell, formatFee, realText, durationLabel, type PublicCourse } from "../../_lib";

const GOLD = "#E8A020";

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
            <Link href={`/academy/register?course=${course.slug}`}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold"
              style={{ background: GOLD, color: "#0A1628" }}>
              Apply now <ArrowRight size={16} />
            </Link>
          </div>
        </aside>
      </div>
    </StorefrontShell>
  );
}
