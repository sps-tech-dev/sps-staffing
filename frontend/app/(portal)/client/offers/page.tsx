"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useClientMe, useClientOffers, useClientReleaseOffer, useClientSetJoiningDate } from "@/lib/api/hooks";
import { FileSignature } from "lucide-react";
import type { ClientOfferRow } from "@/lib/api/types";

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-page text-muted",
  released: "bg-[#EFF6FF] text-[#1B5FE8]",
  accepted: "bg-[#ECFDF5] text-[#059669]",
  declined: "bg-[#FEF2F2] text-[#DC2626]",
  withdrawn: "bg-page text-muted",
};

function money(n: number | null) {
  return n == null ? "—" : `₹${n.toLocaleString("en-IN")}`;
}

/** HR-only editor for one offer. Draft → Release (sets joining date + optional CTC);
 *  released → adjust joining date. A manager never renders this (read-only card). */
function OfferEditor({ offer }: { offer: ClientOfferRow }) {
  const release = useClientReleaseOffer();
  const setJd = useClientSetJoiningDate();
  const [jd, setJd_] = useState(offer.joining_date ?? "");
  const [ctc, setCtc] = useState(offer.ctc != null ? String(offer.ctc) : "");
  const [err, setErr] = useState<string | null>(null);

  if (offer.status !== "draft" && offer.status !== "released") return null; // terminal → no edits

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!jd) { setErr("Joining date is required."); return; }
    const onError = (er: unknown) => setErr((er as { message?: string }).message ?? "Couldn't save.");
    if (offer.status === "draft") {
      release.mutate({ id: offer.id, joining_date: jd, ctc: ctc ? Number(ctc) : undefined }, { onError });
    } else {
      setJd.mutate({ id: offer.id, joining_date: jd }, { onError });
    }
  }
  const pending = release.isPending || setJd.isPending;
  return (
    <form onSubmit={onSubmit} className="mt-2 flex flex-wrap items-end gap-2">
      <label className="text-xs text-muted">Joining date
        <input type="date" value={jd} onChange={(e) => setJd_(e.target.value)}
          className="mt-1 block rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
      </label>
      {offer.status === "draft" && (
        <label className="text-xs text-muted">CTC (optional)
          <input type="number" min={0} value={ctc} onChange={(e) => setCtc(e.target.value)} placeholder="1500000"
            className="mt-1 block w-32 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
        </label>
      )}
      <button type="submit" disabled={pending}
        className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
        {pending ? "Saving…" : offer.status === "draft" ? "Release offer" : "Update joining date"}
      </button>
      {err && <span role="alert" className="text-xs text-[#DC2626]">{err}</span>}
    </form>
  );
}

export default function ClientOffersPage() {
  const me = useClientMe();
  const { data, isLoading, isError, refetch } = useClientOffers();
  const isHR = me.data?.client_role === "client_admin";

  return (
    <AppShell role="client" title="Offers">
      <SectionCard title={isHR ? "Offers — release & manage" : "Offers (read-only)"}>
        <p className="mb-3 text-xs text-muted">
          {isHR
            ? "As HR you can release a draft offer to the candidate and set the joining date."
            : "Your hiring-manager view is read-only. HR releases offers and sets joining dates."}
        </p>
        {isLoading ? <Skeleton className="h-24" />
          : isError || !data ? <p className="text-sm text-muted">Couldn&apos;t load offers. <button onClick={() => refetch()} className="text-[#1B5FE8] underline">Retry</button></p>
          : data.length === 0 ? <EmptyState icon={<FileSignature size={28} />} title="No offers yet" hint="Offers appear here once recruiters raise them." />
          : (
            <div className="divide-y divide-cardline">
              {data.map((o) => (
                <div key={o.id} className="py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-ink">{o.candidate ?? "—"}</div>
                      <div className="mt-0.5 text-xs text-muted">
                        CTC {money(o.ctc)} · Joining {o.joining_date ?? "—"}
                      </div>
                    </div>
                    <span className={`rounded-full px-2 py-0.5 text-xs capitalize ${STATUS_STYLE[o.status] ?? "bg-page text-muted"}`}>{o.status}</span>
                  </div>
                  {isHR && <OfferEditor offer={o} />}
                </div>
              ))}
            </div>
          )}
      </SectionCard>
    </AppShell>
  );
}
