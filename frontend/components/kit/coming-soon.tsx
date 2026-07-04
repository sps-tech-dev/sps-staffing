import Link from "next/link";
import { Hourglass } from "lucide-react";

/** F1: the polished placeholder every not-yet-built deep screen renders.
 *  Later slices replace the page body; nav/entry points stay stable. */
export function ComingSoon({ title, blurb, backHref, backLabel }: {
  title: string; blurb: string; backHref: string; backLabel: string;
}) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="mx-auto max-w-md rounded-2xl border border-cardline bg-card p-10 text-center shadow-sm">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#E8EFFE] text-[#1B5FE8]">
          <Hourglass size={26} />
        </div>
        <h2 className="mt-4 font-display text-lg font-bold text-ink">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">{blurb}</p>
        <p className="mt-1 text-xs text-muted">This area is planned in an upcoming release.</p>
        <Link href={backHref}
          className="mt-6 inline-flex items-center justify-center rounded-lg bg-sps-blue px-4 py-2 text-sm font-medium text-white hover:bg-[#1652c9]">
          {backLabel}
        </Link>
      </div>
    </div>
  );
}
