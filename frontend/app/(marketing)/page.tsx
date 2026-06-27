import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { Briefcase, Code2, GraduationCap } from "lucide-react";

export default async function Home() {
  const t = await getTranslations();
  const services = [
    { key: "staffing", icon: Briefcase },
    { key: "it", icon: Code2 },
    { key: "academy", icon: GraduationCap },
  ] as const;
  const stats = [
    { key: "placements", value: "12k+" },
    { key: "clients", value: "240+" },
    { key: "trained", value: "30k+" },
  ] as const;

  return (
    <main>
      {/* Hero */}
      <section className="mx-auto flex max-w-5xl flex-col items-center gap-6 px-6 py-24 text-center sm:py-28">
        <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-white/40 sm:text-xs">
          {t("hero.eyebrow")}
        </p>
        <h1 className="font-display text-4xl font-extrabold leading-tight sm:text-6xl">
          {t("hero.title1")}<span className="text-sps-sky">{t("hero.title2")}</span>
        </h1>
        <p className="max-w-2xl text-balance text-base text-white/70 sm:text-lg">
          {t("hero.subtitle")}
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-3">
          <Link href="/login?role=candidate" className="rounded-full bg-sps-blue px-6 py-3 text-sm font-semibold">{t("hero.ctaCandidate")}</Link>
          <Link href="/login?role=client" className="rounded-full bg-white/10 px-6 py-3 text-sm font-semibold">{t("hero.ctaEmployer")}</Link>
          <Link href="/candidate" className="rounded-full bg-sps-gold px-6 py-3 text-sm font-semibold text-sps-navy">{t("hero.ctaDemo")}</Link>
        </div>
      </section>

      {/* Services / verticals */}
      <section id="services" className="border-t border-white/10 bg-white/[0.02]">
        <div id="verticals" className="mx-auto max-w-6xl px-6 py-20">
          <div className="mx-auto mb-12 max-w-2xl text-center">
            <h2 className="font-display text-2xl font-bold sm:text-3xl">{t("services.title")}</h2>
            <p className="mt-2 text-sm text-white/60">{t("services.subtitle")}</p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {services.map(({ key, icon: Icon }) => (
              <div key={key} className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                <Icon className="mb-4 h-8 w-8 text-sps-sky" aria-hidden />
                <h3 className="font-display text-lg font-semibold">{t(`services.${key}.name`)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/60">{t(`services.${key}.desc`)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="border-t border-white/10">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <h2 className="mb-10 text-center font-display text-2xl font-bold sm:text-3xl">{t("stats.title")}</h2>
          <div className="grid gap-8 sm:grid-cols-3">
            {stats.map(({ key, value }) => (
              <div key={key} className="text-center">
                <div className="font-display text-4xl font-extrabold text-sps-gold sm:text-5xl">{value}</div>
                <div className="mt-2 text-sm uppercase tracking-wider text-white/50">{t(`stats.${key}`)}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-white/10 bg-sps-blue/10">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 px-6 py-20 text-center">
          <h2 className="font-display text-2xl font-bold sm:text-3xl">{t("cta.title")}</h2>
          <p className="max-w-xl text-sm text-white/60">{t("cta.subtitle")}</p>
          <Link href="/login" className="mt-2 rounded-full bg-sps-blue px-8 py-3 text-sm font-semibold">{t("cta.button")}</Link>
        </div>
      </section>
    </main>
  );
}
