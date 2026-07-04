"use client";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useInvoices, useUpdateInvoice } from "@/lib/api/hooks";
import { Receipt } from "lucide-react";

const STATUSES = ["draft", "issued", "paid", "cancelled"];
const STATUS_STYLE: Record<string, string> = {
  draft: "bg-page text-muted",
  issued: "bg-[#EFF6FF] text-[#1B5FE8]",
  paid: "bg-[#F0FDF4] text-[#16A34A]",
  cancelled: "bg-[#FEF2F2] text-[#DC2626]",
};
const inr = (n: number | null) => (n == null ? "—" : `₹${n.toLocaleString("en-IN")}`);

export default function InvoicesPage() {
  const { data, isLoading, isError, refetch } = useInvoices();
  const update = useUpdateInvoice();

  return (
    <AppShell role="employee" title="Invoices">
      <div className="mb-3 rounded-lg border border-[#E8A020]/40 bg-[#FFFBEB] px-3 py-2 text-xs text-[#8A5A00]">
        Placement fee (15%) is computed. <strong>GST/TDS are not applied until you enter a rate</strong> —
        statutory rates &amp; invoice-compliance specifics await legal confirmation.
      </div>
      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load invoices</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <SectionCard title="Placement invoices">
          {data.length === 0 ? (
            <EmptyState icon={<Receipt size={28} />} title="No invoices yet" hint="Generate an invoice from an accepted offer on the Offers page." />
          ) : (
            <div className="space-y-3">
              {data.map((v) => (
                <div key={v.id} className="rounded-lg border border-cardline p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-ink">{v.candidate ?? "—"} <span className="text-xs text-muted">· {v.job ?? "—"}</span></div>
                      <div className="text-xs text-muted">Base {inr(v.base_amount)} · Fee {v.fee_percent ?? "—"}% = {inr(v.fee_amount)}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-ink">{inr(v.total_amount)}</span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${STATUS_STYLE[v.status]}`}>{v.status}</span>
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                    <label>GST %
                      <input type="number" defaultValue={v.gst_percent ?? ""} placeholder="—"
                        onBlur={(e) => e.target.value && update.mutate({ id: v.id, gst_percent: Number(e.target.value) })}
                        className="ml-1 w-16 rounded border border-cardline bg-white px-1.5 py-0.5 text-ink outline-none focus:border-[#1B5FE8]" />
                    </label>
                    <span>{v.gst_amount != null ? `= ${inr(v.gst_amount)}` : ""}</span>
                    <label>TDS %
                      <input type="number" defaultValue={v.tds_percent ?? ""} placeholder="—"
                        onBlur={(e) => e.target.value && update.mutate({ id: v.id, tds_percent: Number(e.target.value) })}
                        className="ml-1 w-16 rounded border border-cardline bg-white px-1.5 py-0.5 text-ink outline-none focus:border-[#1B5FE8]" />
                    </label>
                    <span>{v.tds_amount != null ? `− ${inr(v.tds_amount)}` : ""}</span>
                    <select value="" onChange={(e) => e.target.value && update.mutate({ id: v.id, status: e.target.value })}
                      className="ml-auto rounded border border-cardline bg-white px-1.5 py-0.5 text-ink outline-none focus:border-[#1B5FE8]" aria-label="Set invoice status">
                      <option value="">Status…</option>
                      {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
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
