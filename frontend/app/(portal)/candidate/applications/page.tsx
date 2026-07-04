"use client";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { useMyApplications } from "@/lib/api/hooks";
import { ClipboardList } from "lucide-react";

const STAGE_LABEL: Record<string, string> = {
  applied: "Applied", screening: "Screening", aptitude_test: "Aptitude Test",
  aptitude_passed: "Aptitude Passed", aptitude_failed: "Aptitude Not Cleared",
  internal_interview: "Internal Interview", internal_passed: "Internal Cleared",
  rtr_pending: "RTR Pending", submitted_to_client: "Submitted to Client",
  client_round_1: "Client Round 1", client_round_2: "Client Round 2",
  client_round_3: "Client Round 3", offer: "Offer", offer_accepted: "Offer Accepted",
  joined: "Joined", guarantee: "Guarantee Period", invoiced: "Joined", paid: "Joined",
  on_hold: "On Hold", withdrawn: "Withdrawn", dropped: "Closed",
};

/** F3b: this candidate's applications with LIVE pipeline stages (B.5 vocabulary,
 *  candidate-friendly labels). An unlinked login or no applications is a valid
 *  state -> friendly empty, never an error. */
export default function MyApplicationsPage() {
  const { data, isLoading, isError } = useMyApplications();
  return (
    <AppShell role="candidate" title="My Applications">
      <SectionCard title="Applications">
        {isLoading ? (
          <Skeleton className="h-32" />
        ) : isError ? (
          <p role="alert" className="rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">
            Couldn&apos;t load your applications — please refresh.
          </p>
        ) : !data || data.length === 0 ? (
          <EmptyState icon={<ClipboardList size={28} />} title="No applications yet"
            hint="When our recruiting team submits you for a role, it appears here with its live status." />
        ) : (
          <div className="divide-y divide-cardline">
            {data.map((a) => (
              <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <p className="text-sm font-medium text-ink">{a.job}</p>
                  {a.applied_at && (
                    <p className="text-xs text-muted">Applied {new Date(a.applied_at).toLocaleDateString()}</p>
                  )}
                </div>
                <StatusPill status={STAGE_LABEL[a.stage] ?? a.stage} />
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </AppShell>
  );
}
