"use client";
/* Public academy student registration (FE surface #2) — creates an academy.students
 * account (A3, SEPARATE from staff auth). Under-18 guardian gate, DPDP consent, dev
 * captcha stub, and college-ID upload via the presign→PUT→submit flow. Consumes
 * GET /register/config, POST /register/id-card/presign, POST /register/student. */
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { StorefrontShell, realText, type PublicCourse } from "../_lib";

const GOLD = "#E8A020";

type Config = {
  hcaptcha_sitekey: string;
  policy_version: string;
  consent_notice: string;
  id_card_content_types: string[];
};

const EMPTY = {
  full_name: "", email: "", phone: "", password: "", student_id: "",
  college_name: "", course_degree: "", year_of_study: "", date_of_birth: "",
  guardian_name: "",
};

function ageFrom(dob: string): number | null {
  if (!dob) return null;
  const d = new Date(dob), t = new Date();
  if (Number.isNaN(d.getTime())) return null;
  let a = t.getFullYear() - d.getFullYear();
  if (t.getMonth() < d.getMonth() || (t.getMonth() === d.getMonth() && t.getDate() < d.getDate())) a--;
  return a;
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold" style={{ color: "#0A1628" }}>{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs" style={{ color: "#9AA6BC" }}>{hint}</span>}
    </label>
  );
}

const inputCls = "w-full rounded-xl border bg-white px-3.5 py-2.5 text-sm outline-none focus:border-[#E8A020]";
const inputStyle = { borderColor: "#DDE3EC", color: "#0A1628" } as const;

function RegisterInner() {
  const params = useSearchParams();
  const courseSlug = params.get("course");
  const next = params.get("next");   // apply intent — threaded on to login so it survives register→login→back
  const [cfg, setCfg] = useState<Config | null>(null);
  const [course, setCourse] = useState<PublicCourse | null>(null);
  const [f, setF] = useState({ ...EMPTY });
  const [idCard, setIdCard] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [guardianConsent, setGuardianConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    api<Config>("/academy/register/config").then(setCfg).catch(() => setCfg(null));
    if (courseSlug) {
      api<PublicCourse>(`/academy/public/courses/${courseSlug}`).then(setCourse).catch(() => setCourse(null));
    }
  }, [courseSlug]);

  const age = useMemo(() => ageFrom(f.date_of_birth), [f.date_of_birth]);
  const isMinor = age !== null && age < 18;
  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  const accept = cfg?.id_card_content_types.join(",") || "application/pdf,image/jpeg,image/png";

  function clientValidate(): string | null {
    for (const [k, v] of Object.entries(f)) {
      if (k === "guardian_name") continue;
      if (!String(v).trim()) return "Please fill in all required fields.";
    }
    if (f.password.length < 12 || !/[A-Za-z]/.test(f.password) || !/\d/.test(f.password))
      return "Password must be at least 12 characters and include a letter and a number.";
    if (!idCard) return "Please upload your college ID card.";
    if (!consent) return "You must consent to data processing to register.";
    if (isMinor && (!f.guardian_name.trim() || !guardianConsent))
      return "Applicants under 18 require a guardian name and guardian consent.";
    return null;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const v = clientValidate();
    if (v) { setError(v); return; }
    setSubmitting(true);
    try {
      // 1) presign → 2) PUT the file to storage → 3) submit with the confirmed key
      const pre = await api<{ upload_url: string; key: string }>(
        "/academy/register/id-card/presign",
        { method: "POST", body: JSON.stringify({ content_type: idCard!.type }) });
      const put = await fetch(pre.upload_url, {
        method: "PUT", body: idCard!, headers: { "Content-Type": idCard!.type } });
      if (!put.ok) throw new ApiError("ID_CARD_UPLOAD_FAILED", "Your ID card couldn't be uploaded. Please try again.");

      await api("/academy/register/student", {
        method: "POST",
        headers: { "Captcha-Token": cfg?.hcaptcha_sitekey ? "" : "dev-test" },
        body: JSON.stringify({
          ...f,
          id_card_key: pre.key,
          consent_data_processing: consent,
          guardian_name: isMinor ? f.guardian_name : null,
          guardian_consent: isMinor ? guardianConsent : null,
        }),
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <StorefrontShell title="You're registered" eyebrow="Training & Internships">
        <div className="mx-auto max-w-lg rounded-2xl bg-white p-10 text-center" style={{ border: "1px solid #EAEEF3" }}>
          <CheckCircle2 size={40} className="mx-auto mb-4" style={{ color: "#16A34A" }} />
          <p className="text-lg font-extrabold" style={{ fontFamily: "'Outfit', sans-serif", color: "#0A1628" }}>
            Your student account is ready
          </p>
          <p className="mt-2 text-sm" style={{ color: "#6B7689" }}>
            We&apos;ve emailed a confirmation. Log in to take your entrance aptitude test.
          </p>
          <Link href={`/academy/login${next ? `?next=${encodeURIComponent(next)}` : ""}`}
            className="mt-6 inline-flex rounded-xl px-5 py-3 text-sm font-semibold"
            style={{ background: GOLD, color: "#0A1628" }}>Log in</Link>
        </div>
      </StorefrontShell>
    );
  }

  const courseTitle = course ? realText(course.title) ?? course.title : null;

  return (
    <StorefrontShell
      title="Create your student account"
      eyebrow="Training & Internships"
      subtitle={courseTitle ? `Applying for ${courseTitle}` : undefined}
    >
      <form onSubmit={onSubmit} className="mx-auto max-w-2xl rounded-2xl bg-white p-8" style={{ border: "1px solid #EAEEF3" }}>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <Field label="Full name"><input className={inputCls} style={inputStyle} value={f.full_name} onChange={set("full_name")} /></Field>
          <Field label="Email"><input type="email" className={inputCls} style={inputStyle} value={f.email} onChange={set("email")} /></Field>
          <Field label="Phone"><input type="tel" className={inputCls} style={inputStyle} value={f.phone} onChange={set("phone")} /></Field>
          <Field label="Password" hint="Min 12 characters, with a letter and a number.">
            <input type="password" className={inputCls} style={inputStyle} value={f.password} onChange={set("password")} />
          </Field>
          <Field label="College ID / roll no."><input className={inputCls} style={inputStyle} value={f.student_id} onChange={set("student_id")} /></Field>
          <Field label="College name"><input className={inputCls} style={inputStyle} value={f.college_name} onChange={set("college_name")} /></Field>
          <Field label="Degree / course"><input className={inputCls} style={inputStyle} value={f.course_degree} onChange={set("course_degree")} /></Field>
          <Field label="Year of study"><input className={inputCls} style={inputStyle} value={f.year_of_study} onChange={set("year_of_study")} /></Field>
          <Field label="Date of birth"><input type="date" className={inputCls} style={inputStyle} value={f.date_of_birth} onChange={set("date_of_birth")} /></Field>
          <Field label="College ID card" hint="PDF, JPEG or PNG (max 5 MB).">
            <input type="file" accept={accept} onChange={(e) => setIdCard(e.target.files?.[0] ?? null)}
              className="w-full text-sm" style={{ color: "#0A1628" }} />
          </Field>
        </div>

        {isMinor && (
          <div className="mt-5 rounded-xl p-4" style={{ background: "#FFFBEB", border: "1px solid #FDE68A" }}>
            <p className="mb-3 text-sm font-semibold" style={{ color: "#92400E" }}>
              You&apos;re under 18 — a parent/guardian must consent on your behalf.
            </p>
            <Field label="Guardian name">
              <input className={inputCls} style={inputStyle} value={f.guardian_name} onChange={set("guardian_name")} />
            </Field>
            <label className="mt-3 flex items-start gap-2 text-sm" style={{ color: "#5A6B8A" }}>
              <input type="checkbox" className="mt-0.5" checked={guardianConsent} onChange={(e) => setGuardianConsent(e.target.checked)} />
              <span>I am the applicant&apos;s parent/guardian and I consent on their behalf.</span>
            </label>
          </div>
        )}

        <label className="mt-6 flex items-start gap-2 text-sm" style={{ color: "#5A6B8A" }}>
          <input type="checkbox" className="mt-0.5" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span>{cfg?.consent_notice ?? "I consent to the processing of my personal data for enrolment."}</span>
        </label>

        <p className="mt-4 text-xs" style={{ color: "#9AA6BC" }}>
          {cfg?.hcaptcha_sitekey
            ? "Protected by hCaptcha."
            : "Captcha runs in dev test mode (no challenge shown locally)."}
        </p>

        {error && (
          <div className="mt-5 rounded-xl px-4 py-3 text-sm" style={{ background: "#FEF2F2", color: "#B91C1C", border: "1px solid #FECACA" }}>
            {error}
          </div>
        )}

        <button type="submit" disabled={submitting}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold disabled:opacity-60"
          style={{ background: GOLD, color: "#0A1628" }}>
          {submitting && <Loader2 size={16} className="animate-spin" />}
          {submitting ? "Creating your account…" : "Create account"}
        </button>
        <p className="mt-3 text-center text-xs" style={{ color: "#9AA6BC" }}>
          Already have an account? <Link href="/academy/login" className="font-semibold" style={{ color: GOLD }}>Log in</Link>
        </p>
      </form>
    </StorefrontShell>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<StorefrontShell title="Create your student account" eyebrow="Training & Internships"><div className="h-96" /></StorefrontShell>}>
      <RegisterInner />
    </Suspense>
  );
}
