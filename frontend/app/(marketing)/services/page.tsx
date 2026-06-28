import Link from "next/link";
import type { Metadata } from "next";
import { ArrowRight, Briefcase, GraduationCap, Code2, Check } from "lucide-react";
import { PageHero } from "../_components/page-hero";
import { Reveal, RevealGroup, RevealItem } from "@/components/marketing/reveal";
import { CTAButton } from "@/components/marketing/ui";

export const metadata: Metadata = {
  title: "Services — SPS Technosoft",
  description: "Three connected verticals on one platform: Staffing & Recruitment, Academy / Training, and IT Consulting.",
};

const SERVICES = [
  {
    icon: Briefcase, name: "Staffing & Recruitment", href: "/staffing-and-recruitment",
    tagline: "Better candidates, faster.",
    desc: "Recruiter expertise paired with AI-assisted matching to deliver higher-quality shortlists, shorter pipelines, and audit-ready operations.",
    points: ["AI-assisted candidate matching", "Vetted, structured submissions", "Kanban pipeline & SLA tracking", "DPDP-conscious by design"],
    cta: "Explore staffing", live: true, accent: "text-sps-blue", ring: "ring-sps-blue/30",
  },
  {
    icon: GraduationCap, name: "Academy / Training", href: "/academy",
    tagline: "Talent, grown in-house.",
    desc: "Upskilling and placement-readiness programs that convert learners into vetted, job-ready candidates feeding straight into the same talent pool.",
    points: ["Role-aligned curricula", "Hands-on, project-based learning", "Placement-readiness tracks", "Graduates flow into staffing"],
    cta: "Coming soon", live: false, accent: "text-sps-gold", ring: "ring-sps-gold/30",
  },
  {
    icon: Code2, name: "IT Consulting", href: "/consulting",
    tagline: "Delivery, from the same bench.",
    desc: "Stand up delivery teams and consulting engagements drawn from the same vetted talent, with the same rigor and operating standards.",
    points: ["Dedicated delivery teams", "Engagement-based consulting", "Shared vetted bench", "Audit-ready operations"],
    cta: "Coming soon", live: false, accent: "text-sps-sky", ring: "ring-sps-sky/30",
  },
];

export default function ServicesPage() {
  return (
    <>
      <PageHero
        eyebrow="Our services"
        title={<>One platform.<br /><span className="text-sps-sky">Three ways to grow talent.</span></>}
        lead="Staffing, training, and consulting are separate businesses that share one vetted talent pool, one technology platform, and one standard of rigor."
      />

      <section className="bg-gradient-to-b from-sps-navy to-[#0a1530]">
        <div className="mx-auto max-w-6xl space-y-10 px-6 py-24 sm:py-28">
          {SERVICES.map((s, i) => {
            const Icon = s.icon;
            return (
              <Reveal key={s.name}>
                <div className="grid items-center gap-8 rounded-3xl border border-white/10 bg-white/[0.03] p-8 sm:p-10 lg:grid-cols-2 lg:gap-12">
                  {/* Visual panel */}
                  <div className={`order-1 ${i % 2 === 1 ? "lg:order-2" : ""}`}>
                    <div className="relative flex aspect-[4/3] items-center justify-center overflow-hidden rounded-2xl bg-gradient-to-br from-white/[0.06] to-transparent ring-1 ring-white/10">
                      <div className={`absolute h-40 w-40 rounded-full bg-current opacity-[0.07] blur-3xl ${s.accent}`} aria-hidden />
                      <div className={`inline-flex h-24 w-24 items-center justify-center rounded-3xl bg-white/[0.04] ring-1 ${s.ring}`}>
                        <Icon className={`h-12 w-12 ${s.accent}`} aria-hidden />
                      </div>
                    </div>
                  </div>
                  {/* Content */}
                  <div className={`order-2 ${i % 2 === 1 ? "lg:order-1" : ""}`}>
                    <div className="flex items-center gap-3">
                      <h2 className="font-display text-2xl font-bold text-white sm:text-3xl">{s.name}</h2>
                      {!s.live && (
                        <span className="rounded-full bg-sps-gold/15 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sps-gold">Soon</span>
                      )}
                    </div>
                    <p className={`mt-1 font-mono text-sm ${s.accent}`}>{s.tagline}</p>
                    <p className="mt-4 text-base leading-relaxed text-white/65">{s.desc}</p>
                    <ul className="mt-6 grid gap-2.5 sm:grid-cols-2">
                      {s.points.map((p) => (
                        <li key={p} className="flex items-start gap-2 text-sm text-white/75">
                          <Check size={16} className={`mt-0.5 shrink-0 ${s.accent}`} aria-hidden />
                          {p}
                        </li>
                      ))}
                    </ul>
                    <div className="mt-8">
                      {s.live ? (
                        <CTAButton href={s.href} variant="primary">{s.cta} <ArrowRight size={16} /></CTAButton>
                      ) : (
                        <Link href={s.href} className="inline-flex items-center gap-1.5 text-sm font-medium text-white/70 hover:text-white">
                          {s.cta} <ArrowRight size={15} />
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </section>

      <section className="border-t border-white/10 bg-sps-navy">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-5 px-6 py-20 text-center">
          <Reveal>
            <h2 className="font-display text-2xl font-bold text-white sm:text-3xl">Not sure which fits?</h2>
          </Reveal>
          <Reveal delay={0.08}>
            <p className="max-w-lg text-white/65">Start with staffing, or talk to us about a combined approach.</p>
          </Reveal>
          <Reveal delay={0.16}>
            <RevealGroup className="flex flex-wrap justify-center gap-3">
              <RevealItem><CTAButton href="/staffing-and-recruitment" variant="primary">Staffing &amp; Recruitment</CTAButton></RevealItem>
              <RevealItem><CTAButton href="/contact" variant="ghost">Contact us</CTAButton></RevealItem>
            </RevealGroup>
          </Reveal>
        </div>
      </section>
    </>
  );
}
