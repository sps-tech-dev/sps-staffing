import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowRight, Building2, UserRound, IdCard, ClipboardList, Cpu, FileCheck2,
  CalendarCheck, Handshake, Gauge, Target, ShieldCheck, ScanSearch, Layers, BadgeCheck,
} from "lucide-react";
import { VideoHero } from "@/components/marketing/video-hero";
import { Reveal, RevealGroup, RevealItem } from "@/components/marketing/reveal";
import { SectionHeading, Eyebrow, CTAButton } from "@/components/marketing/ui";

export const metadata: Metadata = {
  title: "Staffing & Recruitment — SPS Technosoft",
  description:
    "Better candidates, faster. Recruiter expertise plus AI-assisted matching for higher-quality hires — with a kanban pipeline, vetted submissions, and DPDP-conscious operations.",
};

const PROBLEMS = [
  { icon: ScanSearch, title: "Inconsistent screening", desc: "Quality swings recruiter to recruiter. We standardize screening with structured, AI-assisted matching against the real requirement." },
  { icon: Gauge, title: "Slow pipelines", desc: "Roles stay open for weeks. We compress sourcing-to-shortlist with automation that surfaces the strongest fits first." },
  { icon: Target, title: "Variable quality", desc: "Too many near-misses. We optimize for signal — fewer, better submissions you can actually act on." },
];

const STEPS = [
  { icon: ClipboardList, n: "01", t: "Intake", d: "We capture the role, must-haves, and context — so matching is grounded in what actually matters." },
  { icon: Cpu, n: "02", t: "AI-assisted matching", d: "Candidates are matched on skills and fit, then ranked — recruiters review the strongest first." },
  { icon: FileCheck2, n: "03", t: "Vetted submissions", d: "Only structured, screened candidates reach you — each with a clear, reviewable profile." },
  { icon: CalendarCheck, n: "04", t: "Interviews", d: "Schedule and track interviews in one pipeline, with status visible to everyone involved." },
  { icon: Handshake, n: "05", t: "Offer & placement", d: "Release offers, set joining dates, and close the loop — all on one auditable system." },
];

const WHY = [
  { icon: Layers, title: "One pipeline, full visibility", desc: "A kanban pipeline with SLA tracking — every candidate, every stage, in one place." },
  { icon: BadgeCheck, title: "Quality you can defend", desc: "Structured screening and AI-assisted ranking mean shortlists you can stand behind." },
  { icon: ShieldCheck, title: "DPDP-conscious by design", desc: "Consent on record, PII encrypted at rest, append-only audit trails — privacy isn't bolted on." },
];

const ROLES = [
  { icon: Building2, title: "Client Login", desc: "Review submissions, run your pipeline, release offers.", href: "/login?role=client", variant: "primary" as const },
  { icon: UserRound, title: "Candidate Login", desc: "Track your applications and interviews.", href: "/login?role=candidate", variant: "gold" as const },
  { icon: IdCard, title: "Employee Login", desc: "Recruiters & staff — manage requisitions and delivery.", href: "/login?role=employee", variant: "ghost" as const },
];

export default function StaffingPage() {
  return (
    <>
      {/* ── Staffing video hero ─────────────────────────────────── */}
      <VideoHero>
        <div className="max-w-3xl">
          <Reveal><Eyebrow>Staffing &amp; Recruitment</Eyebrow></Reveal>
          <Reveal delay={0.08}>
            <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.05] text-white sm:text-6xl lg:text-7xl">
              Better candidates,<br /><span className="text-sps-sky">faster.</span>
            </h1>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-6 max-w-2xl text-pretty text-base leading-relaxed text-white/80 sm:text-xl">
              Experienced recruiters plus AI-assisted matching — for higher-quality hires, shorter
              pipelines, and operations you can audit end to end.
            </p>
          </Reveal>
          <Reveal delay={0.24}>
            <div className="mt-9 flex flex-wrap gap-3">
              <CTAButton href="/register/client" variant="gold">Post a job <ArrowRight size={16} /></CTAButton>
              <CTAButton href="#login" variant="ghost">Sign in to your portal</CTAButton>
            </div>
          </Reveal>
        </div>
      </VideoHero>

      {/* ── Problems we solve ───────────────────────────────────── */}
      <section className="bg-gradient-to-b from-sps-navy to-[#0a1530]">
        <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
          <Reveal>
            <SectionHeading light eyebrow="The problem" title="Hiring is broken in three familiar ways"
              lead="And each one quietly costs you good candidates. Here's how we fix them." />
          </Reveal>
          <RevealGroup className="mt-14 grid gap-6 md:grid-cols-3">
            {PROBLEMS.map(({ icon: Icon, title, desc }) => (
              <RevealItem key={title}>
                <div className="h-full rounded-2xl border border-white/10 bg-white/[0.03] p-7">
                  <Icon className="mb-4 h-8 w-8 text-sps-gold" aria-hidden />
                  <h3 className="font-display text-lg font-semibold text-white">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/60">{desc}</p>
                </div>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* ── How it works ────────────────────────────────────────── */}
      <section className="border-t border-white/10 bg-[#0a1530]">
        <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
          <Reveal>
            <SectionHeading light eyebrow="How it works" title="Intake to offer, on one system"
              lead="A clear, repeatable flow — every step tracked, every handoff visible." />
          </Reveal>
          <RevealGroup className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
            {STEPS.map(({ icon: Icon, n, t, d }) => (
              <RevealItem key={n}>
                <div className="relative h-full rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                  <span className="font-mono text-xs text-sps-sky">{n}</span>
                  <Icon className="mt-3 h-7 w-7 text-sps-blue" aria-hidden />
                  <h3 className="mt-3 font-display text-base font-semibold text-white">{t}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/55">{d}</p>
                </div>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* ── Why SPS ─────────────────────────────────────────────── */}
      <section className="border-t border-white/10 bg-sps-navy">
        <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
          <Reveal>
            <SectionHeading light eyebrow="Why SPS" title="The advantages that compound" />
          </Reveal>
          <RevealGroup className="mt-14 grid gap-6 md:grid-cols-3">
            {WHY.map(({ icon: Icon, title, desc }) => (
              <RevealItem key={title}>
                <div className="h-full rounded-2xl border border-white/10 bg-white/[0.03] p-7">
                  <Icon className="mb-4 h-8 w-8 text-sps-sky" aria-hidden />
                  <h3 className="font-display text-lg font-semibold text-white">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/60">{desc}</p>
                </div>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* ── Placement model as value ────────────────────────────── */}
      <section className="border-t border-white/10 bg-[#0a1530]">
        <div className="mx-auto max-w-5xl px-6 py-24 sm:py-28">
          <Reveal>
            <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-sps-blue/15 to-transparent p-8 text-center sm:p-12">
              <Eyebrow className="!text-sps-gold">Aligned incentives</Eyebrow>
              <h2 className="mx-auto mt-4 max-w-2xl font-display text-2xl font-bold leading-snug text-white sm:text-3xl">
                You pay for outcomes, not activity.
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-white/65">
                Our placement-based model means we only succeed when you make a great hire who stays.
                That keeps us focused on quality and fit — not filling your inbox with résumés.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── Login entries (THE entry point for the 3 roles) ─────── */}
      <section id="login" className="scroll-mt-20 border-t border-white/10 bg-gradient-to-br from-sps-blue/15 via-sps-navy to-sps-navy">
        <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
          <Reveal>
            <SectionHeading light eyebrow="Portals" title="Sign in to your portal"
              lead="Three roles, three workspaces — all on the same secure, tenant-isolated platform." />
          </Reveal>

          <RevealGroup className="mt-14 grid gap-6 md:grid-cols-3">
            {ROLES.map(({ icon: Icon, title, desc, href, variant }) => (
              <RevealItem key={title}>
                <div className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.04] p-7 text-center">
                  <span className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/[0.05] ring-1 ring-white/10">
                    <Icon className="h-7 w-7 text-sps-sky" aria-hidden />
                  </span>
                  <h3 className="mt-5 font-display text-lg font-semibold text-white">{title}</h3>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-white/60">{desc}</p>
                  <div className="mt-6">
                    <CTAButton href={href} variant={variant} className="w-full">{title} <ArrowRight size={15} /></CTAButton>
                  </div>
                </div>
              </RevealItem>
            ))}
          </RevealGroup>

          <Reveal delay={0.1}>
            <div className="mt-12 flex flex-col items-center gap-3 rounded-2xl border border-sps-gold/25 bg-sps-gold/10 px-6 py-8 text-center sm:flex-row sm:justify-between sm:text-left">
              <div>
                <h3 className="font-display text-lg font-semibold text-white">New here? Hiring for a role?</h3>
                <p className="mt-1 text-sm text-white/70">Register your company and post your first job — we&apos;ll take it from there.</p>
              </div>
              <Link
                href="/register/client"
                className="inline-flex shrink-0 items-center gap-2 rounded-full bg-sps-gold px-6 py-3 text-sm font-semibold text-sps-navy shadow-lg shadow-sps-gold/25 transition hover:bg-sps-gold/90"
              >
                Post a job <ArrowRight size={16} />
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </>
  );
}
