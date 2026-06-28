import Link from "next/link";
import type { Metadata } from "next";
import { ArrowRight, Briefcase, GraduationCap, Code2, ShieldCheck, Zap, Users2, LineChart } from "lucide-react";
import { VideoHero } from "@/components/marketing/video-hero";
import { Reveal, RevealGroup, RevealItem } from "@/components/marketing/reveal";
import { SectionHeading, Eyebrow, CTAButton } from "@/components/marketing/ui";

export const metadata: Metadata = {
  title: "SPS Technosoft — Staffing, Training & IT Consulting",
  description:
    "SPS Technosoft Pvt Ltd is a multi-vertical technology company spanning staffing & recruitment, training, and IT consulting — built on one engineering-grade talent platform.",
};

const VERTICALS = [
  {
    icon: Briefcase, name: "Staffing & Recruitment", href: "/staffing-and-recruitment",
    desc: "Recruiter expertise plus AI-assisted matching — higher-quality hires, faster pipelines, audit-ready operations.",
    accent: "text-sps-blue", live: true,
  },
  {
    icon: GraduationCap, name: "Academy / Training", href: "/academy",
    desc: "Upskilling and placement-readiness programs that turn learners into vetted, job-ready talent.",
    accent: "text-sps-gold", live: false,
  },
  {
    icon: Code2, name: "IT Consulting", href: "/consulting",
    desc: "Delivery teams and consulting engagements drawn from the same vetted bench, with the same rigor.",
    accent: "text-sps-sky", live: false,
  },
];

const VALUES = [
  { icon: Zap, title: "Speed without shortcuts", desc: "Faster shortlists through automation — never at the cost of screening quality or candidate experience." },
  { icon: ShieldCheck, title: "Compliance by design", desc: "DPDP-conscious from day one: consent on record, PII encrypted at rest, append-only audit trails." },
  { icon: Users2, title: "One talent platform", desc: "Staffing, training, and consulting run on a single shared talent pool and one operating system." },
  { icon: LineChart, title: "Engineered to scale", desc: "Multi-tenant, isolation-tested architecture that grows with every client and every vertical." },
];

const STATS = [
  { value: "3", label: "Connected verticals" },
  { value: "1", label: "Shared talent platform" },
  { value: "DPDP", label: "Compliance-first" },
  { value: "24/7", label: "Audit-ready operations" },
];

export default function CorporateHome() {
  return (
    <>
      {/* ── Video hero ─────────────────────────────────────────── */}
      <VideoHero>
        <div className="max-w-3xl">
          <Reveal>
            <Eyebrow>SPS Technosoft Pvt Ltd</Eyebrow>
          </Reveal>
          <Reveal delay={0.08}>
            <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.05] text-white sm:text-6xl lg:text-7xl">
              Talent, technology,<br />
              <span className="text-sps-sky">engineered together.</span>
            </h1>
          </Reveal>
          <Reveal delay={0.16}>
            <p className="mt-6 max-w-2xl text-pretty text-base leading-relaxed text-white/80 sm:text-xl">
              We help companies build great teams — through staffing &amp; recruitment, training,
              and IT consulting — all running on one engineering-grade talent platform.
            </p>
          </Reveal>
          <Reveal delay={0.24}>
            <div className="mt-9 flex flex-wrap gap-3">
              <CTAButton href="/services" variant="primary">
                Explore our services <ArrowRight size={16} />
              </CTAButton>
              <CTAButton href="/staffing-and-recruitment" variant="ghost">
                Staffing &amp; Recruitment
              </CTAButton>
            </div>
          </Reveal>
        </div>
      </VideoHero>

      {/* ── Company intro ──────────────────────────────────────── */}
      <section className="bg-sps-navy">
        <div className="mx-auto max-w-5xl px-6 py-24 sm:py-28">
          <Reveal className="text-center">
            <Eyebrow className="!text-sps-gold">Who we are</Eyebrow>
            <p className="mx-auto mt-5 max-w-3xl text-balance font-display text-2xl font-semibold leading-snug text-white sm:text-3xl">
              SPS Technosoft is a multi-vertical technology company. We bring recruiter craft and
              modern automation together so that hiring, training, and delivery all draw from{" "}
              <span className="text-sps-sky">one vetted talent pool</span>.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ── What we do — 3 verticals ───────────────────────────── */}
      <section className="border-t border-white/10 bg-gradient-to-b from-sps-navy to-[#0a1530]">
        <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
          <Reveal>
            <SectionHeading
              light
              eyebrow="What we do"
              title="Three verticals, one platform"
              lead="Each business stands on its own — and shares the same talent, technology, and standards."
            />
          </Reveal>

          <RevealGroup className="mt-14 grid gap-6 md:grid-cols-3">
            {VERTICALS.map(({ icon: Icon, name, href, desc, accent, live }) => (
              <RevealItem key={name}>
                <Link
                  href={href}
                  className="group flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.03] p-7 transition-all duration-300 hover:-translate-y-1 hover:border-white/20 hover:bg-white/[0.06]"
                >
                  <div className="mb-5 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-white/[0.06] ring-1 ring-white/10">
                    <Icon className={`h-6 w-6 ${accent}`} aria-hidden />
                  </div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-display text-lg font-semibold text-white">{name}</h3>
                    {!live && (
                      <span className="rounded-full bg-sps-gold/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sps-gold">
                        Soon
                      </span>
                    )}
                  </div>
                  <p className="mt-3 flex-1 text-sm leading-relaxed text-white/60">{desc}</p>
                  <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-sps-sky">
                    {live ? "Explore" : "Learn more"}
                    <ArrowRight size={15} className="transition-transform duration-200 group-hover:translate-x-1" />
                  </span>
                </Link>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* ── Why SPS ────────────────────────────────────────────── */}
      <section className="border-t border-white/10 bg-[#0a1530]">
        <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
          <Reveal>
            <SectionHeading
              light
              eyebrow="Why SPS"
              title="Built like a product, run like a partner"
              lead="The discipline of an engineering team, applied to the business of finding and growing talent."
            />
          </Reveal>

          <RevealGroup className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {VALUES.map(({ icon: Icon, title, desc }) => (
              <RevealItem key={title}>
                <div className="h-full rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                  <Icon className="mb-4 h-7 w-7 text-sps-gold" aria-hidden />
                  <h3 className="font-display text-base font-semibold text-white">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/60">{desc}</p>
                </div>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* ── Stats band ─────────────────────────────────────────── */}
      <section className="border-t border-white/10 bg-sps-navy">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <RevealGroup className="grid grid-cols-2 gap-8 lg:grid-cols-4">
            {STATS.map(({ value, label }) => (
              <RevealItem key={label} className="text-center">
                <div className="font-display text-4xl font-extrabold text-sps-gold sm:text-5xl">{value}</div>
                <div className="mt-2 text-xs uppercase tracking-wider text-white/50 sm:text-sm">{label}</div>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* ── Closing CTA ────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-t border-white/10 bg-gradient-to-br from-sps-blue/20 via-sps-navy to-sps-navy">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-6 px-6 py-24 text-center sm:py-28">
          <Reveal>
            <h2 className="font-display text-3xl font-extrabold leading-tight text-white sm:text-4xl">
              Let&apos;s build your team.
            </h2>
          </Reveal>
          <Reveal delay={0.08}>
            <p className="max-w-xl text-base text-white/70">
              Tell us what you&apos;re hiring for, or explore how our verticals work together.
            </p>
          </Reveal>
          <Reveal delay={0.16}>
            <div className="flex flex-wrap justify-center gap-3">
              <CTAButton href="/contact" variant="primary">Contact us <ArrowRight size={16} /></CTAButton>
              <CTAButton href="/services" variant="ghost">See our services</CTAButton>
            </div>
          </Reveal>
        </div>
      </section>
    </>
  );
}
