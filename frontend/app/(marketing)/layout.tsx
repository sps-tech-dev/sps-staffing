import Link from "next/link";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import { CompanyLogo } from "@/components/kit/company-logo";
import { LocaleSwitcher } from "@/components/marketing/locale-switcher";

export default async function MarketingLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();
  const t = await getTranslations("nav");
  const year = 2026;

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <div lang={locale} className="flex min-h-dvh flex-col bg-sps-navy text-white">
        <header className="border-b border-white/10">
          <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
            <Link href="/" className="flex items-center gap-2.5">
              <CompanyLogo size={32} />
              <span className="font-display text-sm font-bold tracking-tight">
                SPS<span className="text-sps-sky">Technosoft</span>
              </span>
            </Link>
            <div className="flex items-center gap-5">
              <a href="#services" className="hidden text-sm text-white/70 hover:text-white sm:inline">{t("services")}</a>
              <a href="#verticals" className="hidden text-sm text-white/70 hover:text-white sm:inline">{t("verticals")}</a>
              <a href="#contact" className="hidden text-sm text-white/70 hover:text-white sm:inline">{t("contact")}</a>
              <LocaleSwitcher />
              <Link href="/login" className="rounded-full bg-sps-blue px-4 py-2 text-sm font-semibold">{t("login")}</Link>
            </div>
          </nav>
        </header>

        <div className="flex-1">{children}</div>

        <footer id="contact" className="border-t border-white/10">
          <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-8 text-center sm:flex-row sm:text-left">
            <div className="flex items-center gap-2.5">
              <CompanyLogo size={24} />
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-white/40">
                {(await getTranslations("footer"))("tagline")}
              </span>
            </div>
            <p className="text-xs text-white/40">
              © {year} SPS Technosoft. {(await getTranslations("footer"))("rights")}
            </p>
          </div>
        </footer>
      </div>
    </NextIntlClientProvider>
  );
}
