import type { Metadata } from "next";
import { Rocket, HeartHandshake, TrendingUp, BriefcaseBusiness, Mail } from "lucide-react";
import { PageHero } from "../_components/page-hero";
import { Reveal, RevealGroup, RevealItem } from "@/components/marketing/reveal";
import { SectionHeading, CTAButton } from "@/components/marketing/ui";

export const metadata: Metadata = {
  title: "Career — SPS Technosoft",
  description: "Build your career at SPS Technosoft — recruiters, engineers, trainers, and consultants building one talent platform.",
};

const WHY = [
  { icon: Rocket, title: "Build something real", desc: "Ship a product that places people in jobs and powers three businesses — not a side project." },
  { icon: TrendingUp, title: "Grow fast", desc: "Small, high-trust team. Ownership from day one, and room to move across verticals." },
  { icon: HeartHandshake, title: "Work that matters", desc: "Every feature affects a real candidate's career and a real client's team." },
];

export default function CareerPage() {
  return (
    <>
      <PageHero
        eyebrow="Careers"
        title={<>Help us build the<br /><span className="text-sps-sky">talent platform.</span></>}
        lead="We're a small, engineering-grade team spanning recruiting, software, training, and consulting. If you care about quality and people, you'll fit right in."
      >
        <CTAButton href="#openings" variant="primary">See open roles</CTAButton>
        <CTAButton href="/contact" variant="ghost">Get in touch</CTAButton>
      </PageHero>

      {/* Why join */}
      <section className="bg-gradient-to-b from-sps-navy to-[#0a1530]">
        <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
          <Reveal>
            <SectionHeading light eyebrow="Why SPS" title="A place to do your best work"
              lead="High standards, real ownership, and a mission you can explain to your family in one sentence." />
          </Reveal>
          <RevealGroup className="mt-14 grid gap-6 md:grid-cols-3">
            {WHY.map(({ icon: Icon, title, desc }) => (
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

      {/* Openings — empty/placeholder state */}
      <section id="openings" className="scroll-mt-24 border-t border-white/10 bg-[#0a1530]">
        <div className="mx-auto max-w-4xl px-6 py-24 sm:py-28">
          <Reveal>
            <SectionHeading light eyebrow="Open roles" title="Current openings" />
          </Reveal>
          <Reveal delay={0.1}>
            <div className="mt-12 flex flex-col items-center rounded-3xl border border-dashed border-white/15 bg-white/[0.02] px-6 py-16 text-center">
              <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/[0.04] ring-1 ring-white/10">
                <BriefcaseBusiness className="h-7 w-7 text-sps-sky" aria-hidden />
              </div>
              <h3 className="mt-5 font-display text-xl font-semibold text-white">No open roles right now</h3>
              <p className="mt-2 max-w-md text-sm text-white/60">
                We&apos;re not actively hiring at the moment — but we&apos;re always glad to meet
                talented people. Send us your profile and we&apos;ll reach out when something fits.
              </p>
              <a
                href="mailto:careers@spstechnosoft.com"
                className="mt-6 inline-flex items-center gap-2 rounded-full bg-sps-blue px-6 py-3 text-sm font-semibold text-white transition hover:bg-sps-blue/90"
              >
                <Mail size={16} /> careers@spstechnosoft.com
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      {/* How to apply */}
      <section className="border-t border-white/10 bg-sps-navy">
        <div className="mx-auto max-w-4xl px-6 py-20">
          <Reveal>
            <SectionHeading light align="left" eyebrow="How to apply"
              title="Three simple steps"
              lead="No black-hole applications. We read everything and reply." />
          </Reveal>
          <RevealGroup className="mt-10 grid gap-6 sm:grid-cols-3">
            {[
              { n: "01", t: "Send your profile", d: "Email careers@spstechnosoft.com with your CV or LinkedIn and a line about what you want to build." },
              { n: "02", t: "Intro conversation", d: "A relaxed chat about your work, our mission, and whether there's a fit." },
              { n: "03", t: "Practical round", d: "A real-world exercise close to the actual job — no trick puzzles." },
            ].map((s) => (
              <RevealItem key={s.n}>
                <div className="h-full rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                  <span className="font-mono text-sm text-sps-gold">{s.n}</span>
                  <h3 className="mt-2 font-display text-base font-semibold text-white">{s.t}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/60">{s.d}</p>
                </div>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>
    </>
  );
}
