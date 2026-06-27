"use client";

import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import clsx from "clsx";

const OPTIONS = [
  { code: "en", label: "EN" },
  { code: "hi", label: "हिं" },
] as const;

export function LocaleSwitcher() {
  const active = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function select(code: string) {
    if (code === active) return;
    // Persist for 1 year; read back by i18n/request.ts on the next request.
    document.cookie = `NEXT_LOCALE=${code}; path=/; max-age=31536000; samesite=lax`;
    startTransition(() => router.refresh());
  }

  return (
    <div
      className="flex items-center gap-1 rounded-full border border-white/15 p-0.5"
      role="group"
      aria-label="Language"
      aria-busy={pending}
    >
      {OPTIONS.map((o) => (
        <button
          key={o.code}
          type="button"
          onClick={() => select(o.code)}
          aria-pressed={active === o.code}
          className={clsx(
            "rounded-full px-2.5 py-1 text-xs font-semibold transition-colors disabled:opacity-50",
            active === o.code ? "bg-white text-sps-navy" : "text-white/70 hover:text-white",
          )}
          disabled={pending}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
