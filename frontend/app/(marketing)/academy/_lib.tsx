"use client";
/* Public academy storefront — shared types/helpers/primitives (FE surface #1).
 * Consumes the A2 public endpoints; renders only what the safe-fields DTO returns. */
import Link from "next/link";
import { motion } from "framer-motion";
import { GraduationCap } from "lucide-react";

/** Exact shape returned by GET /api/academy/public/courses[/{slug}]
 *  (backend _public_course_dict — the allowlisted safe DTO). */
export type PublicCourse = {
  title: string;
  slug: string;
  description: string | null;
  syllabus: string | null;
  level: string | null;
  duration_weeks: number | null;
  fee: number;
  currency: string;
  next_cohort_start: string | null;
};

/** A field is a placeholder when null/blank or a bracketed authoring marker like
 *  "[YOUR CONTENT — placeholder]" / "[SAMPLE …]" — render a neutral fallback, never
 *  the raw marker or an empty gap. */
export function isPlaceholder(v: string | null | undefined): boolean {
  if (v == null) return true;
  const s = v.trim();
  return s === "" || /^\[.*\]$/.test(s) || s.startsWith("[YOUR CONTENT") || s.startsWith("[SAMPLE");
}

export function realText(v: string | null | undefined): string | null {
  return isPlaceholder(v) ? null : (v as string).trim();
}

/** Fee formatted from the row's OWN currency + amount — never a hardcoded ₹ or number. */
export function formatFee(fee: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency", currency, maximumFractionDigits: 0,
    }).format(fee);
  } catch {
    return `${currency} ${fee.toLocaleString("en-IN")}`;
  }
}

export function durationLabel(weeks: number | null): string | null {
  return weeks && weeks > 0 ? `${weeks} week${weeks === 1 ? "" : "s"}` : null;
}

const GOLD = "#E8A020";

/** Local FadeIn matching the marketing design primitive (kept tiny to avoid pulling
 *  the whole _design/site module into the storefront bundle). */
export function FadeIn({ children, delay = 0, className = "" }:
  { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }} transition={{ duration: 0.5, delay }} className={className}>
      {children}
    </motion.div>
  );
}

export function CourseCard({ c }: { c: PublicCourse }) {
  const blurb = realText(c.description);
  const dur = durationLabel(c.duration_weeks);
  const level = realText(c.level);
  return (
    <Link href={`/academy/courses/${c.slug}`} className="group block h-full">
      <div className="flex h-full flex-col rounded-2xl p-7 transition-shadow group-hover:shadow-lg"
        style={{ background: "#F0F4FA", border: "1px solid rgba(232,160,32,0.15)" }}>
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl"
          style={{ background: "#FBEFD7" }}>
          <GraduationCap size={22} style={{ color: GOLD }} />
        </div>
        <h3 className="mb-2 text-xl font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
          {c.title}
        </h3>
        <p className="mb-5 flex-1 text-sm leading-relaxed" style={{ color: "#5A6B8A" }}>
          {blurb ?? "Programme details coming soon."}
        </p>
        <div className="flex items-center gap-3 text-xs" style={{ color: "#6B7689" }}>
          {dur && <span>{dur}</span>}
          {dur && level && <span>·</span>}
          {level && <span>{level}</span>}
        </div>
        <div className="mt-4 flex items-center justify-between">
          <span className="text-lg font-extrabold" style={{ color: "#0A1628" }}>
            {formatFee(c.fee, c.currency)}
          </span>
          <span className="text-sm font-semibold group-hover:underline" style={{ color: GOLD }}>
            View details →
          </span>
        </div>
      </div>
    </Link>
  );
}

/** Shared page shell for the storefront (gold-accent hero band + light canvas),
 *  matching the education marketing surface. */
export function StorefrontShell({ eyebrow, title, subtitle, children, back }:
  { eyebrow?: string; title: string; subtitle?: string; children: React.ReactNode; back?: React.ReactNode }) {
  return (
    <div>
      <section className="pt-24 pb-12" style={{ background: "linear-gradient(135deg, #1A1408 0%, #2E2207 60%, #5A3F0B 100%)" }}>
        <div className="mx-auto max-w-7xl px-6">
          {back}
          {eyebrow && (
            <span className="mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-bold"
              style={{ background: "rgba(232,160,32,0.2)", color: "#F6C667", border: "1px solid rgba(232,160,32,0.3)" }}>
              <GraduationCap size={12} /> {eyebrow}
            </span>
          )}
          <h1 className="text-4xl font-extrabold text-white lg:text-5xl" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {title}
          </h1>
          {subtitle && <p className="mt-4 max-w-2xl text-lg" style={{ color: "#E8C98A" }}>{subtitle}</p>}
        </div>
      </section>
      <section className="py-16" style={{ background: "#F0F4FA" }}>
        <div className="mx-auto max-w-7xl px-6">{children}</div>
      </section>
    </div>
  );
}
