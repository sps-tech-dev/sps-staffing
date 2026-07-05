"use client";
/* Public academy storefront — course listing (/academy). Renders published courses
 * from GET /api/academy/public/courses. Loading / error / empty states handled. */
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { CourseCard, FadeIn, StorefrontShell, type PublicCourse } from "./_lib";

export default function AcademyStorefront() {
  const [courses, setCourses] = useState<PublicCourse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api<PublicCourse[]>("/academy/public/courses")
      .then((d) => { if (alive) setCourses(d); })
      .catch((e) => { if (alive) setError(e instanceof ApiError ? e.message : "Something went wrong"); });
    return () => { alive = false; };
  }, []);

  return (
    <StorefrontShell
      eyebrow="Training & Internships"
      title="Courses & Programmes"
      subtitle="Industry-led certification tracks with hands-on projects and placement assistance."
    >
      {error ? (
        <div className="rounded-2xl bg-white p-10 text-center" style={{ border: "1px solid #EAEEF3" }}>
          <p className="font-semibold" style={{ color: "#0A1628" }}>We couldn&apos;t load the courses right now.</p>
          <p className="mt-1 text-sm" style={{ color: "#6B7689" }}>{error}. Please try again shortly.</p>
        </div>
      ) : courses === null ? (
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-64 animate-pulse rounded-2xl" style={{ background: "#E7ECF3" }} />
          ))}
        </div>
      ) : courses.length === 0 ? (
        <div className="rounded-2xl bg-white p-14 text-center" style={{ border: "1px solid #EAEEF3" }}>
          <p className="text-lg font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
            No courses published yet
          </p>
          <p className="mt-2 text-sm" style={{ color: "#6B7689" }}>
            New programmes are on the way — check back soon.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3">
          {courses.map((c, i) => (
            <FadeIn key={c.slug} delay={i * 0.06}>
              <CourseCard c={c} />
            </FadeIn>
          ))}
        </div>
      )}
    </StorefrontShell>
  );
}
