import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { SiteHeader } from "@/components/marketing/site-header";
import { SiteFooter } from "@/components/marketing/site-footer";

/** Corporate marketing shell: fixed transparent header (no login) over the page,
 *  then content, then the corporate footer. The next-intl provider is preserved so
 *  the app's locale plumbing stays intact (marketing copy itself is English-first). */
export default async function MarketingLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <div lang={locale} className="flex min-h-dvh flex-col bg-sps-navy text-white">
        <SiteHeader />
        <main className="flex-1">{children}</main>
        <SiteFooter />
      </div>
    </NextIntlClientProvider>
  );
}
