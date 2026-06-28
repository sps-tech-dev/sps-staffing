"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useClientRegistrations, useApproveClient, useRejectClient } from "@/lib/api/hooks";
import { Building2, Check, X } from "lucide-react";

export default function ClientRegistrationsPage() {
  const { data, isLoading, isError, refetch } = useClientRegistrations("pending");
  const approve = useApproveClient();
  const reject = useRejectClient();
  const [pw, setPw] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);

  function onApprove(id: string) {
    setErr(null);
    const password = pw[id] || "";
    if (password.length < 12) { setErr("Set an initial password (min 12 chars) before approving."); return; }
    approve.mutate({ id, create_new_client: true, initial_password: password },
      { onError: (e) => setErr((e as { message?: string }).message ?? "Approval failed.") });
  }

  return (
    <AppShell role="admin" title="Client registrations">
      <p className="mb-3 text-sm text-muted">
        Approving <strong>links the registrant to a client company and activates their login</strong> — the
        security gate that binds a login to a client scope. Set an initial password; the client signs in with it.
      </p>
      {err && <p role="alert" className="mb-3 rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">{err}</p>}
      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>
      ) : isError || !data ? (
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="font-display font-semibold text-ink">Couldn&apos;t load registrations</p>
          <button onClick={() => refetch()} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
        </div>
      ) : (
        <SectionCard title={`Pending (${data.total})`}>
          {data.items.length === 0 ? (
            <EmptyState icon={<Building2 size={28} />} title="No pending client registrations" hint="New company sign-ups awaiting approval appear here." />
          ) : (
            <div className="space-y-3">
              {data.items.map((r) => (
                <div key={r.id} className="rounded-lg border border-cardline p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-ink">{r.company_name} <span className="text-xs font-normal text-muted">· {r.industry ?? "—"} · {r.company_size ?? "—"}</span></div>
                      <div className="text-xs text-muted">{r.contact_person} · {r.email} · {r.phone ?? "—"}{r.website ? ` · ${r.website}` : ""}</div>
                    </div>
                    <span className="rounded-full bg-[#FFFBEB] px-2 py-0.5 text-xs font-semibold text-[#E8A020]">pending</span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <input type="password" placeholder="Initial password (12+ chars)" value={pw[r.id] ?? ""}
                      onChange={(e) => setPw((m) => ({ ...m, [r.id]: e.target.value }))}
                      className="w-56 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
                    <button onClick={() => onApprove(r.id)} disabled={approve.isPending}
                      className="inline-flex items-center gap-1 rounded-lg bg-[#16A34A] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-60">
                      <Check size={14} /> Approve &amp; create client
                    </button>
                    <button onClick={() => reject.mutate(r.id)} disabled={reject.isPending}
                      className="inline-flex items-center gap-1 rounded-lg border border-[#DC2626]/40 px-3 py-1.5 text-sm font-semibold text-[#DC2626]">
                      <X size={14} /> Reject
                    </button>
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
