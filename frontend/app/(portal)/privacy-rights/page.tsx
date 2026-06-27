"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { ShieldCheck, Download, Trash2, FileClock } from "lucide-react";
import {
  useConsent, useSetConsent, useExportData, useRequestErasure, useDpdpRequests,
} from "@/lib/api/hooks";

const PURPOSE_LABELS: Record<string, string> = {
  data_processing: "Essential data processing",
  marketing: "Marketing communications",
  cookies: "Non-essential cookies",
};

export default function PrivacyRightsPage() {
  const consent = useConsent();
  const setConsent = useSetConsent();
  const exportData = useExportData();
  const erasure = useRequestErasure();
  const requests = useDpdpRequests();
  const [eraseConfirm, setEraseConfirm] = useState(false);

  function onExport() {
    exportData.mutate(undefined, {
      onSuccess: (res) => {
        // Right to portability — hand the principal their data as a JSON download.
        const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "my-data-export.json"; a.click();
        URL.revokeObjectURL(url);
      },
    });
  }

  return (
    <AppShell role="candidate" title="Privacy & Your Rights">
      {/* STOP-3: legal wording is stubbed — mechanism only. */}
      <div className="mb-4 rounded-lg border border-[#E8A020]/40 bg-[#FFFBEB] px-4 py-3 text-sm text-[#8A5A00]">
        <strong>Draft notices.</strong> The legal wording below is a placeholder
        (<code>[LEGAL COPY TBD]</code>) pending review. The consent, export, and
        erasure mechanisms are live.
      </div>

      {/* Consent */}
      <SectionCard title="Your consent">
        {consent.isLoading ? (
          <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : consent.isError || !consent.data ? (
          <p className="text-sm text-muted">Couldn&apos;t load your consent settings.</p>
        ) : (
          <div className="divide-y divide-cardline">
            {Object.keys(consent.data.purposes).map((purpose) => {
              const granted = consent.data!.purposes[purpose];
              return (
                <div key={purpose} className="flex items-start justify-between gap-4 py-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm font-medium text-ink">
                      <ShieldCheck size={16} className="text-[#1B5FE8]" />
                      {PURPOSE_LABELS[purpose] ?? purpose}
                    </div>
                    <p className="mt-1 text-xs text-muted">{consent.data!.notices[purpose]}</p>
                  </div>
                  <label className="flex shrink-0 cursor-pointer items-center gap-2 text-xs text-muted">
                    <input
                      type="checkbox"
                      checked={granted}
                      disabled={setConsent.isPending}
                      onChange={(e) => setConsent.mutate({ purpose, granted: e.target.checked })}
                      className="h-4 w-4 accent-[#1B5FE8]"
                    />
                    {granted ? "Granted" : "Off"}
                  </label>
                </div>
              );
            })}
            <p className="pt-3 text-xs text-muted">Policy version: {consent.data.policy_version}</p>
          </div>
        )}
      </SectionCard>

      {/* Data rights */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <SectionCard title="Export my data">
          <p className="mb-3 text-sm text-muted">Download a copy of your account, profile, and applications.</p>
          <button
            onClick={onExport}
            disabled={exportData.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            <Download size={16} /> {exportData.isPending ? "Preparing…" : "Export (JSON)"}
          </button>
        </SectionCard>

        <SectionCard title="Request erasure">
          <p className="mb-3 text-sm text-muted">Request deletion of your data. We&apos;ll record and review the request.</p>
          {!eraseConfirm ? (
            <button
              onClick={() => setEraseConfirm(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-[#DC2626]/40 px-4 py-2 text-sm font-semibold text-[#DC2626]"
            >
              <Trash2 size={16} /> Request erasure
            </button>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-ink">Are you sure?</span>
              <button
                onClick={() => erasure.mutate(undefined, { onSettled: () => setEraseConfirm(false) })}
                disabled={erasure.isPending}
                className="rounded-lg bg-[#DC2626] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {erasure.isPending ? "Submitting…" : "Confirm"}
              </button>
              <button onClick={() => setEraseConfirm(false)} className="rounded-lg border border-cardline px-3 py-2 text-sm text-muted">Cancel</button>
            </div>
          )}
        </SectionCard>
      </div>

      {/* History */}
      <div className="mt-6">
        <SectionCard title="Request history">
          {requests.isLoading ? (
            <Skeleton className="h-16" />
          ) : requests.isError || !requests.data ? (
            <p className="text-sm text-muted">Couldn&apos;t load your requests.</p>
          ) : requests.data.items.length === 0 ? (
            <EmptyState icon={<FileClock size={28} />} title="No requests yet" hint="Your export and erasure requests appear here." />
          ) : (
            <div className="divide-y divide-cardline">
              {requests.data.items.map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-2 py-2.5 text-sm">
                  <span className="font-medium text-ink capitalize">{r.kind}</span>
                  <div className="flex items-center gap-3 text-xs text-muted">
                    <span>{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</span>
                    <span className="rounded-full bg-page px-2 py-0.5 capitalize">{r.status}</span>
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
