import type { ReactNode } from "react";
import { Reveal } from "@/components/marketing/reveal";
import { Eyebrow } from "@/components/marketing/ui";

/** Compact inner-page hero (no video) — sits under the fixed header with a navy
 *  gradient + subtle gold glow. Used by /about, /services, /career, /contact. */
export function PageHero({
  eyebrow, title, lead, children,
}: { eyebrow: string; title: ReactNode; lead?: ReactNode; children?: ReactNode }) {
  return (
    <section className="relative overflow-hidden border-b border-white/10 bg-sps-navy">
      <div
        className="pointer-events-none absolute -top-32 left-1/2 h-72 w-[42rem] -translate-x-1/2 rounded-full bg-sps-blue/20 blur-[120px]"
        aria-hidden
      />
      <div className="relative mx-auto max-w-5xl px-6 pb-16 pt-36 text-center sm:pb-20 sm:pt-44">
        <Reveal><Eyebrow>{eyebrow}</Eyebrow></Reveal>
        <Reveal delay={0.08}>
          <h1 className="mx-auto mt-4 max-w-3xl font-display text-4xl font-extrabold leading-[1.08] text-white sm:text-5xl lg:text-6xl">
            {title}
          </h1>
        </Reveal>
        {lead && (
          <Reveal delay={0.16}>
            <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-relaxed text-white/70 sm:text-lg">
              {lead}
            </p>
          </Reveal>
        )}
        {children && <Reveal delay={0.24}><div className="mt-8 flex flex-wrap justify-center gap-3">{children}</div></Reveal>}
      </div>
    </section>
  );
}
