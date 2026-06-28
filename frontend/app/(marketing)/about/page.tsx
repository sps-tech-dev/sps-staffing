import type { Metadata } from "next";
import { Target, Compass, Layers, Heart, ShieldCheck, Sparkles } from "lucide-react";
import { PageHero } from "../_components/page-hero";
import { Reveal, RevealGroup, RevealItem } from "@/components/marketing/reveal";
import { SectionHeading, CTAButton } from "@/components/marketing/ui";

export const metadata: Metadata = {
  title: "About — SPS Technosoft",
  description: "The story, mission, and multi-vertical model behind SPS Technosoft Pvt Ltd.",
};

const VALUES = [
  { icon: Heart, title: "People first", desc: "Every placement is a person's career and a company's team. We treat both with care." },
  { icon: ShieldCheck, title: "Integrity & privacy", desc: "Consent on record, PII encrypted, audit trails that can't be quietly edited. Trust is engineered in." },
  { icon: Sparkles, title: "Quality over volume", desc: "We optimize for the right hire, not the most résumés. Better signal, every time." },
  { icon: Layers, title: "One platform, many outcomes", desc: "Staffing, training, and consulting reinforce each other on shared infrastructure." },
];

export default function AboutPage() {
  return (
    <>
      <PageHero
        eyebrow="About us"
        title={<>We build teams,<br /><span className="text-sps-sky">and the platform behind them.</span></>}
        lead="SPS Technosoft Pvt Ltd is a multi-vertical technology company. We bring recruiter craft and modern engineering together so hiring, training, and delivery all draw from one vetted talent pool."
      />

      {/* Story + mission */}
      <section className="bg-gradient-to-b from-sps-navy to-[#0a1530]">
        <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
          <div className="grid gap-12 lg:grid-cols-2">
            <Reveal>
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-8 sm:p-10">
                <Target className="h-9 w-9 text-sps-blue" aria-hidden />
                <h2 className="mt-5 font-display text-2xl font-bold text-white">Our mission</h2>
                <p className="mt-4 text-base leading-relaxed text-white/65">
                  Make great hiring repeatable. We pair experienced recruiters with AI-assisted
                  matching so that every shortlist is higher quality, every pipeline is faster, and
                  every step is transparent and compliant.
                </p>
              </div>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-8 sm:p-10">
                <Compass className="h-9 w-9 text-sps-gold" aria-hidden />
                <h2 className="mt-5 font-display text-2xl font-bold text-white">Our model</h2>
                <p className="mt-4 text-base leading-relaxed text-white/65">
                  Three verticals — staffing &amp; recruitment, training, and IT consulting — built on
                  one shared talent pool and one operating system. Learners become candidates;
                  candidates become delivery teams. The platform compounds.
                </p>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* Values */}
      <section className="border-t border-white/10 bg-[#0a1530]">
        <div className="mx-auto max-w-6xl px-6 py-24 sm:py-28">
          <Reveal>
            <SectionHeading light eyebrow="What we stand for" title="Values we engineer in"
              lead="Not posters on a wall — these show up in the product, the data model, and the way we work." />
          </Reveal>
          <RevealGroup className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {VALUES.map(({ icon: Icon, title, desc }) => (
              <RevealItem key={title}>
                <div className="h-full rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                  <Icon className="mb-4 h-7 w-7 text-sps-sky" aria-hidden />
                  <h3 className="font-display text-base font-semibold text-white">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/60">{desc}</p>
                </div>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-white/10 bg-sps-navy">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-5 px-6 py-20 text-center">
          <Reveal><h2 className="font-display text-2xl font-bold text-white sm:text-3xl">Want to work with us — or for us?</h2></Reveal>
          <Reveal delay={0.08}>
            <div className="flex flex-wrap justify-center gap-3">
              <CTAButton href="/services" variant="primary">Our services</CTAButton>
              <CTAButton href="/career" variant="ghost">Careers at SPS</CTAButton>
            </div>
          </Reveal>
        </div>
      </section>
    </>
  );
}
