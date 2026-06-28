import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { ArrowLeft } from "lucide-react";
import { Reveal } from "@/components/marketing/reveal";
import { Eyebrow, CTAButton } from "@/components/marketing/ui";

/** Minimal on-brand "Coming soon" page for verticals not yet built (Academy, Consulting). */
export function ComingSoon({
  icon: Icon, eyebrow, title, blurb, accent = "text-sps-gold",
}: { icon: LucideIcon; eyebrow: string; title: ReactNode; blurb: string; accent?: string }) {
  return (
    <section className="relative flex min-h-[100svh] items-center overflow-hidden bg-sps-navy">
      <div className="pointer-events-none absolute left-1/2 top-1/3 h-80 w-[44rem] -translate-x-1/2 rounded-full bg-sps-blue/15 blur-[130px]" aria-hidden />
      <div className="relative mx-auto max-w-2xl px-6 py-32 text-center">
        <Reveal>
          <div className="mx-auto inline-flex h-20 w-20 items-center justify-center rounded-3xl bg-white/[0.04] ring-1 ring-white/10">
            <Icon className={`h-10 w-10 ${accent}`} aria-hidden />
          </div>
        </Reveal>
        <Reveal delay={0.08}><Eyebrow className="mt-8">{eyebrow}</Eyebrow></Reveal>
        <Reveal delay={0.14}>
          <h1 className="mt-4 font-display text-4xl font-extrabold leading-tight text-white sm:text-5xl">{title}</h1>
        </Reveal>
        <Reveal delay={0.2}>
          <p className="mx-auto mt-5 max-w-md text-base leading-relaxed text-white/65">{blurb}</p>
        </Reveal>
        <Reveal delay={0.28}>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <CTAButton href="/services" variant="ghost"><ArrowLeft size={16} /> Back to services</CTAButton>
            <CTAButton href="/contact" variant="primary">Get notified</CTAButton>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
