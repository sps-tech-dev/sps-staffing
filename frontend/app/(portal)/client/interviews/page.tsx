"use client";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { useClientInterviews } from "@/lib/api/hooks";
import { CalendarClock } from "lucide-react";

/** F4: the client's scheduled interviews (read-only; scheduling is coordinated
 *  by the recruiting team — calendar invites arrive by email/.ics). */
export default function ClientInterviewsPage() {
  const { data, isLoading, isError, refetch } = useClientInterviews();
  return (
    <AppShell role="client" title="Interviews">
      <SectionCard title="Scheduled interviews">
        {isLoading ? <Skeleton className="h-24" />
          : isError || !data ? (
            <p className="text-sm text-muted">Couldn&apos;t load interviews.{" "}
              <button onClick={() => refetch()} className="text-[#1B5FE8] underline">Retry</button></p>
          ) : data.length === 0 ? (
            <EmptyState icon={<CalendarClock size={28} />} title="No interviews scheduled"
              hint="Interviews for your candidates appear here once scheduled." />
          ) : (
            <div className="divide-y divide-cardline">
              {data.map((iv) => (
                <div key={iv.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div>
                    <p className="text-sm font-medium text-ink">{iv.candidate ?? "—"}</p>
                    <p className="text-xs text-muted">
                      {iv.scheduled_at ? new Date(iv.scheduled_at).toLocaleString() : "Time to be confirmed"}
                      {iv.mode && ` · ${iv.mode}`}
                    </p>
                  </div>
                  <StatusPill status={iv.status} />
                </div>
              ))}
            </div>
          )}
      </SectionCard>
    </AppShell>
  );
}
