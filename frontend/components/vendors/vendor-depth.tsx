"use client";
import { useState } from "react";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { KpiGrid } from "@/components/widgets/kpi-grid";
import {
  useCreateVendorContract, useMarkCommissionPaid, useSetVendorClientRate, useStaffClients,
  useVendorClientRates, useVendorCommissions, useVendorContracts, useVendorScorecard,
  useVoidCommission,
} from "@/lib/api/hooks";
import type { Vendor, VendorCommission } from "@/lib/api/types";
import { FileSignature, Handshake, IndianRupee, Timer, TrendingUp } from "lucide-react";

const inr = (n: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);

/** F6 (B.13 depth): contracts, the vendor×client rate matrix, the commission
 *  ledger (accrued→paid|void — paid can never be voided here; the control
 *  disappears, mirroring the backend rule), and the read-only scorecard. */
export function VendorDepth({ vendor }: { vendor: Vendor }) {
  const contracts = useVendorContracts(vendor.id);
  const rates = useVendorClientRates(vendor.id);
  const commissions = useVendorCommissions(vendor.id);
  const scorecard = useVendorScorecard(vendor.id);
  const clients = useStaffClients();
  const createContract = useCreateVendorContract();
  const setRate = useSetVendorClientRate();
  const markPaid = useMarkCommissionPaid();
  const voidComm = useVoidCommission();

  const [pct, setPct] = useState("");
  const [from, setFrom] = useState("");
  const [until, setUntil] = useState("");
  const [rateClient, setRateClient] = useState("");
  const [ratePct, setRatePct] = useState("");
  const [voiding, setVoiding] = useState<VendorCommission | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const clientName = (id: string) =>
    clients.data?.find((c) => c.id === id)?.name ?? `${id.slice(0, 8)}…`;

  return (
    <div className="mt-6 space-y-6">
      <h2 className="font-display text-base font-bold text-ink">Manage: {vendor.name}</h2>
      {err && <p role="alert" className="rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">{err}</p>}

      {/* scorecard */}
      <SectionCard title="Scorecard">
        {scorecard.isLoading ? <Skeleton className="h-20" /> : scorecard.data && (
          <KpiGrid items={[
            { value: `${scorecard.data.submissions} → ${scorecard.data.placements}`, label: "Submissions → placements", icon: <Handshake size={20} />, accent: "#1B5FE8" },
            { value: scorecard.data.conversion_rate != null ? `${(scorecard.data.conversion_rate * 100).toFixed(0)}%` : "—", label: "Conversion", icon: <TrendingUp size={20} />, accent: "#16A34A" },
            { value: scorecard.data.avg_time_to_fill_days ?? "—", label: "Avg time-to-fill (days)", icon: <Timer size={20} />, accent: "#7C3AED" },
            { value: inr(scorecard.data.commission_accrued + scorecard.data.commission_paid), label: "Commission (accrued + paid)", icon: <IndianRupee size={20} />, accent: "#E8A020" },
          ]} />
        )}
      </SectionCard>

      {/* contracts */}
      <SectionCard title="Contracts (base commission)">
        <form className="mb-3 flex flex-wrap items-end gap-2" noValidate
          onSubmit={(e) => { e.preventDefault(); setErr(null);
            createContract.mutate({ vendorId: vendor.id, base_commission_percent: Number(pct),
              valid_from: from, valid_until: until || undefined },
              { onSuccess: () => { setPct(""); setFrom(""); setUntil(""); },
                onError: (er) => setErr((er as Error).message ?? "Couldn't create the contract.") }); }}>
          <label className="text-xs text-muted">Base %
            <input type="number" step="0.5" value={pct} onChange={(e) => setPct(e.target.value)}
              className="mt-1 block w-20 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink" />
          </label>
          <label className="text-xs text-muted">Valid from
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
              className="mt-1 block rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink" />
          </label>
          <label className="text-xs text-muted">Until (optional)
            <input type="date" value={until} onChange={(e) => setUntil(e.target.value)}
              className="mt-1 block rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink" />
          </label>
          <button type="submit" disabled={!pct || !from || createContract.isPending}
            className="rounded-lg bg-sps-blue px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">
            Add contract
          </button>
        </form>
        {contracts.isLoading ? <Skeleton className="h-12" />
          : !contracts.data || contracts.data.length === 0 ? (
            <p className="text-xs text-muted">No contracts — without one (or a client rate/override), commission accrual is refused by design.</p>
          ) : (
            <div className="divide-y divide-cardline text-sm">
              {contracts.data.map((c) => (
                <div key={c.id} className="flex items-center justify-between py-2">
                  <span className="text-ink">{Number(c.base_commission_percent)}% of placement fee</span>
                  <span className="text-xs text-muted">{c.valid_from} → {c.valid_until ?? "open-ended"} · {c.status}</span>
                </div>
              ))}
            </div>
          )}
      </SectionCard>

      {/* client-rate matrix */}
      <SectionCard title="Per-client rates (beat the contract base)">
        <form className="mb-3 flex flex-wrap items-end gap-2" noValidate
          onSubmit={(e) => { e.preventDefault(); setErr(null);
            setRate.mutate({ vendorId: vendor.id, client_id: rateClient, commission_percent: Number(ratePct) },
              { onSuccess: () => { setRateClient(""); setRatePct(""); },
                onError: (er) => setErr((er as Error).message ?? "Couldn't set the rate.") }); }}>
          <label className="text-xs text-muted">Client
            <select value={rateClient} onChange={(e) => setRateClient(e.target.value)}
              className="mt-1 block w-48 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink">
              <option value="">Select client…</option>
              {(clients.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="text-xs text-muted">Rate %
            <input type="number" step="0.5" value={ratePct} onChange={(e) => setRatePct(e.target.value)}
              className="mt-1 block w-20 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink" />
          </label>
          <button type="submit" disabled={!rateClient || !ratePct || setRate.isPending}
            className="rounded-lg bg-sps-blue px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">
            Set rate
          </button>
        </form>
        {rates.isLoading ? <Skeleton className="h-10" />
          : !rates.data || rates.data.length === 0 ? (
            <p className="text-xs text-muted">No per-client overrides — the contract base applies.</p>
          ) : (
            <div className="divide-y divide-cardline text-sm">
              {rates.data.map((r) => (
                <div key={r.client_id} className="flex items-center justify-between py-2">
                  <span className="text-ink">{clientName(r.client_id)}</span>
                  <span className="font-semibold text-ink">{Number(r.commission_percent)}%</span>
                </div>
              ))}
            </div>
          )}
      </SectionCard>

      {/* commission ledger */}
      <SectionCard title="Commission ledger">
        {commissions.isLoading ? <Skeleton className="h-16" />
          : !commissions.data || commissions.data.length === 0 ? (
            <EmptyState icon={<FileSignature size={28} />} title="No commissions yet"
              hint="Commissions accrue from vendor-sourced placements (fee × resolved rate)." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-cardline text-xs uppercase tracking-wide text-muted">
                    <th className="py-2 pr-3">Placement</th><th className="py-2 pr-3">Rate</th>
                    <th className="py-2 pr-3">Fee base</th><th className="py-2 pr-3">Commission</th>
                    <th className="py-2 pr-3">Status</th><th className="py-2">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cardline">
                  {commissions.data.map((c) => (
                    <tr key={c.id}>
                      <td className="py-2 pr-3 font-mono text-xs text-muted">{c.placement_id.slice(0, 8)}…</td>
                      <td className="py-2 pr-3 text-ink">{Number(c.resolved_percent)}%</td>
                      <td className="py-2 pr-3 text-ink">{inr(Number(c.base_amount))}</td>
                      <td className="py-2 pr-3 font-semibold text-ink">{inr(Number(c.commission_amount))}</td>
                      <td className="py-2 pr-3">
                        <span className={
                          c.status === "paid" ? "rounded-full bg-[#F0FDF4] px-2 py-0.5 text-[11px] font-semibold text-[#16A34A]"
                          : c.status === "void" ? "rounded-full bg-page px-2 py-0.5 text-[11px] font-semibold text-muted"
                          : "rounded-full bg-[#EFF6FF] px-2 py-0.5 text-[11px] font-semibold text-[#1B5FE8]"
                        }>{c.status}</span>
                        {c.status === "void" && c.void_reason && (
                          <p className="mt-0.5 text-[11px] text-muted">“{c.void_reason}”</p>
                        )}
                      </td>
                      <td className="py-2">
                        {/* accrued → may be paid or voided; paid/void → NO controls
                            (paid can't be voided — the backend rule, mirrored) */}
                        {c.status === "accrued" ? (
                          <span className="flex gap-2">
                            <button onClick={() => markPaid.mutate(c.id, { onError: (er) => setErr((er as Error).message) })}
                              className="rounded-lg border border-[#16A34A]/40 px-2 py-0.5 text-xs font-semibold text-[#16A34A]">
                              Mark paid
                            </button>
                            <button onClick={() => { setVoiding(c); setVoidReason(""); }}
                              className="rounded-lg border border-[#DC2626]/40 px-2 py-0.5 text-xs font-semibold text-[#DC2626]">
                              Void…
                            </button>
                          </span>
                        ) : <span className="text-xs text-muted">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </SectionCard>

      {voiding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-sm rounded-2xl border border-cardline bg-card p-5 shadow-lg">
            <h3 className="font-display text-base font-bold text-ink">Void commission — reason required</h3>
            <textarea value={voidReason} onChange={(e) => setVoidReason(e.target.value)} rows={3} autoFocus
              placeholder="e.g. placement fee credit-noted"
              className="mt-3 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setVoiding(null)} className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-page">Cancel</button>
              <button disabled={!voidReason.trim() || voidComm.isPending}
                onClick={() => voidComm.mutate({ id: voiding.id, reason: voidReason.trim() },
                  { onSuccess: () => setVoiding(null), onError: (er) => { setErr((er as Error).message); setVoiding(null); } })}
                className="rounded-lg bg-[#DC2626] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">
                Confirm void
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
