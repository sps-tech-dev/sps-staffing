import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

// i18n without locale routing (F5): the marketing site resolves its locale from a
// cookie (NEXT_LOCALE), defaulting to English. i18n is scoped to the (marketing)
// route group via its own layout; the authenticated app keeps its single root
// layout + auth middleware untouched. See docs/DECISIONS.md.
export const LOCALES = ["en", "hi"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "NEXT_LOCALE";

function coerce(value: string | undefined): Locale {
  return (LOCALES as readonly string[]).includes(value ?? "")
    ? (value as Locale)
    : DEFAULT_LOCALE;
}

export default getRequestConfig(async () => {
  const store = await cookies();
  const locale = coerce(store.get(LOCALE_COOKIE)?.value);
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
