"use client";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useState } from "react";
import { useOffers, useUpdateOffer, useCreateInvoice } from "@/lib/api/hooks";
import { FileSignature, CheckCircle2, Receipt } from "lucide-react";

const STATUSES = ["draft", "released", "accepted", "declined", "withdrawn"];
const STATUS_STYLE: Record<string, string> = {
  draft: "bg-page text-muted",
  released: "bg-[#EFF6FF] text-[#1B5FE8]",
  accepted: "bg-[#F0FDF4] text-[#16A34A]",
  declined: "bg-[#FEF2F2] text-[#DC2626]",
  withdrawn: "bg-[#FFFBEB] text-[#E8A020]",
};

export default function OffersPage() {
  const { data, isLoading, isError, refetch } = useOffers();
  const update = useUpdateOffer();
  const createInvoice = useCreateInvoice();
  const [invoiced, setInvoiced] = useState<Record<string, boolean>>({});

  return (
    <AppShell role="client" title="Offers">
      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load offers</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <SectionCard title="Offers">
          {data.length === 0 ? (
            <EmptyState icon={<FileSignature size={28} />} title="No offers yet" hint="Make an offer from the pipeline board (offer stage)." />
          ) : (
            <div className="divide-y divide-cardline">
              {data.map((o) => (
                <div key={o.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ink">{o.candidate ?? "—"}</div>
                    <div className="text-xs text-muted">{o.job ?? "—"}</div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-muted">
                      {o.rtr_signed_at && <span className="inline-flex items-center gap-1 text-[#16A34A]"><CheckCircle2 size={12} /> RTR</span>}
                      {o.accepted_at && <span className="text-[#16A34A]">Accepted</span>}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <label className="text-xs text-muted">₹
                      <input type="number" defaultValue={o.ctc ?? ""} placeholder="CTC"
                        onBlur={(e) => e.target.value && update.mutate({ id: o.id, ctc: Number(e.target.value) })}
                        className="ml-1 w-24 rounded-lg border border-cardline bg-white px-2 py-1 text-ink outline-none focus:border-[#1B5FE8]" />
                    </label>
                    <input type="date" defaultValue={o.joining_date ?? ""}
                      onChange={(e) => e.target.value && update.mutate({ id: o.id, joining_date: e.target.value })}
                      className="rounded-lg border border-cardline bg-white px-2 py-1 text-xs text-ink outline-none focus:border-[#1B5FE8]" />
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${STATUS_STYLE[o.status]}`}>{o.status}</span>
                    <select value="" onChange={(e) => e.target.value && update.mutate({ id: o.id, status: e.target.value })}
                      className="rounded-lg border border-cardline bg-white px-2 py-1 text-xs text-ink outline-none focus:border-[#1B5FE8]" aria-label="Set offer status">
                      <option value="">Status…</option>
                      {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                    {!o.rtr_signed_at && (
                      <button onClick={() => update.mutate({ id: o.id, rtr_signed: true })}
                        className="rounded-lg border border-cardline px-2 py-1 text-xs font-medium text-ink">Mark RTR signed</button>
                    )}
                    {o.status === "accepted" && o.ctc != null && (
                      <button
                        onClick={() => createInvoice.mutate({ application_id: o.application_id, base_amount: o.ctc! },
                          { onSuccess: () => setInvoiced((m) => ({ ...m, [o.id]: true })) })}
                        disabled={invoiced[o.id]}
                        className="inline-flex items-center gap-1 rounded-lg bg-[#16A34A] px-2 py-1 text-xs font-semibold text-white disabled:opacity-50">
                        <Receipt size={12} /> {invoiced[o.id] ? "Invoiced" : "Generate invoice"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      )}
    </AppShell>
  );
}
