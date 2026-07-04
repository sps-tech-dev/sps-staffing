"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { StatusPill } from "@/components/kit/status-pill";
import { useJobs, useCreateJob } from "@/lib/api/hooks";
import { Briefcase } from "lucide-react";

export default function JobsPage() {
  const { data, isLoading, isError } = useJobs();
  const create = useCreateJob();
  const [title, setTitle] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const t = title.trim();
    if (!t) return;
    try {
      await create.mutateAsync({ title: t });
      setTitle("");
    } catch {
      /* surfaced below via create.isError */
    }
  }

  return (
    <AppShell role="employee" title="Jobs">
      <SectionCard title="Post a job">
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
          <input
            autoFocus value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="Job title (e.g. Senior Python Developer)"
            className="flex-1 rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]"
          />
          <button type="submit" disabled={create.isPending}
            className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {create.isPending ? "Adding…" : "Add job"}
          </button>
        </form>
        {create.isError && <p role="alert" className="mt-2 text-sm text-[#DC2626]">Couldn&apos;t create the job. Please retry.</p>}
      </SectionCard>

      <div className="mt-6">
        <SectionCard title="Open & recent jobs">
          {isLoading ? (
            <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
          ) : isError || !data ? (
            <p className="py-6 text-center text-sm text-muted">Couldn&apos;t load jobs.</p>
          ) : data.length === 0 ? (
            <EmptyState icon={<Briefcase size={28} />} title="No jobs yet" hint="Post your first job above." />
          ) : (
            <div className="divide-y divide-cardline">
              {data.map((j) => (
                <div key={j.id} className="flex items-center justify-between py-3">
                  <span className="text-sm text-ink">{j.title}</span>
                  <StatusPill status={j.status} />
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </AppShell>
  );
}
