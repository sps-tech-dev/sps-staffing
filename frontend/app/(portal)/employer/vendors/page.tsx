"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import {
  useVendors, useCreateVendor, useUpdateVendor, useVendorSubmissions, useUpdateVendorSubmission,
} from "@/lib/api/hooks";
import { Building2, Handshake } from "lucide-react";

const VSTATUS = ["submitted", "shortlisted", "rejected", "placed"];

export default function VendorsPage() {
  const vendors = useVendors();
  const subs = useVendorSubmissions();
  const createVendor = useCreateVendor();
  const updateVendor = useUpdateVendor();
  const updateSub = useUpdateVendorSubmission();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [commission, setCommission] = useState("");

  function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    createVendor.mutate(
      { name: name.trim(), contact_email: email || undefined, commission_percent: commission ? Number(commission) : undefined },
      { onSuccess: () => { setName(""); setEmail(""); setCommission(""); } },
    );
  }

  return (
    <AppShell role="employee" title="Vendors">
      <SectionCard title="Add vendor / sub-vendor">
        <form onSubmit={onCreate} className="flex flex-wrap items-end gap-2" noValidate>
          <label className="text-xs text-muted">Name
            <input value={name} autoFocus onChange={(e) => setName(e.target.value)} placeholder="Partner Agency"
              className="mt-1 block w-48 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
          </label>
          <label className="text-xs text-muted">Contact email
            <input value={email} type="email" onChange={(e) => setEmail(e.target.value)} placeholder="ops@partner.com"
              className="mt-1 block w-48 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
          </label>
          <label className="text-xs text-muted">Commission %
            <input value={commission} type="number" onChange={(e) => setCommission(e.target.value)} placeholder="8"
              className="mt-1 block w-24 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
          </label>
          <button type="submit" disabled={createVendor.isPending}
            className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {createVendor.isPending ? "Adding…" : "Add vendor"}
          </button>
        </form>
      </SectionCard>

      <div className="mt-6">
        <SectionCard title="Vendors">
          {vendors.isLoading ? <Skeleton className="h-20" />
            : vendors.isError || !vendors.data ? <p className="text-sm text-muted">Couldn&apos;t load vendors.</p>
            : vendors.data.length === 0 ? <EmptyState icon={<Building2 size={28} />} title="No vendors yet" hint="Add a partner agency above." />
            : (
              <div className="divide-y divide-cardline">
                {vendors.data.map((v) => (
                  <div key={v.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-ink">{v.name}</div>
                      <div className="text-xs text-muted">{v.contact_email ?? "—"}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-muted">Comm %
                        <input type="number" defaultValue={v.commission_percent ?? ""}
                          onBlur={(e) => e.target.value && updateVendor.mutate({ id: v.id, commission_percent: Number(e.target.value) })}
                          className="ml-1 w-16 rounded border border-cardline bg-white px-1.5 py-0.5 text-ink outline-none focus:border-[#1B5FE8]" />
                      </label>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${v.status === "active" ? "bg-[#F0FDF4] text-[#16A34A]" : "bg-page text-muted"}`}>{v.status}</span>
                      <button onClick={() => updateVendor.mutate({ id: v.id, status: v.status === "active" ? "inactive" : "active" })}
                        className="rounded-lg border border-cardline px-2 py-1 text-xs text-ink">{v.status === "active" ? "Deactivate" : "Activate"}</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
        </SectionCard>
      </div>

      <div className="mt-6">
        <SectionCard title="Vendor submissions (attribution)">
          {subs.isLoading ? <Skeleton className="h-16" />
            : subs.isError || !subs.data ? <p className="text-sm text-muted">Couldn&apos;t load vendor submissions.</p>
            : subs.data.length === 0 ? <EmptyState icon={<Handshake size={28} />} title="No vendor submissions yet" hint="Vendor-attributed candidate submissions appear here." />
            : (
              <div className="divide-y divide-cardline">
                {subs.data.map((s) => (
                  <div key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                    <span className="text-ink"><span className="font-medium">{s.candidate}</span> <span className="text-xs text-muted">via {s.vendor}</span></span>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-page px-2 py-0.5 text-xs capitalize text-muted">{s.status}</span>
                      <select value="" onChange={(e) => e.target.value && updateSub.mutate({ id: s.id, status: e.target.value })}
                        className="rounded border border-cardline bg-white px-1.5 py-0.5 text-xs text-ink outline-none focus:border-[#1B5FE8]" aria-label="Set status">
                        <option value="">Status…</option>
                        {VSTATUS.map((st) => <option key={st} value={st}>{st}</option>)}
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            )}
        </SectionCard>
      </div>
    </AppShell>
  );
}
