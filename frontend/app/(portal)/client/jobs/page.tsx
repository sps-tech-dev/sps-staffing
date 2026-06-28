"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useClientJobs, useClientPostJob } from "@/lib/api/hooks";
import { Briefcase } from "lucide-react";

export default function ClientJobsPage() {
  const { data, isLoading, isError, refetch } = useClientJobs();
  const post = useClientPostJob();
  const [title, setTitle] = useState("");
  const [jd, setJd] = useState("");
  const [skills, setSkills] = useState("");
  const [err, setErr] = useState<string | null>(null);

  function onPost(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setErr(null);
    post.mutate(
      { title: title.trim(), jd_text: jd || undefined, skills: skills ? skills.split(",").map((s) => s.trim()).filter(Boolean) : undefined },
      { onSuccess: () => { setTitle(""); setJd(""); setSkills(""); }, onError: (e) => setErr((e as { message?: string }).message ?? "Couldn't post the job.") },
    );
  }

  return (
    <AppShell role="client" title="Your jobs">
      <SectionCard title="Post a new job">
        <p className="mb-3 text-xs text-muted">Posts to our recruiters&apos; queue. They&apos;ll source and submit candidates against it.</p>
        {err && <p role="alert" className="mb-2 rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">{err}</p>}
        <form onSubmit={onPost} className="flex flex-wrap items-end gap-2" noValidate>
          <label className="text-xs text-muted">Title
            <input value={title} autoFocus onChange={(e) => setTitle(e.target.value)} placeholder="Senior Backend Engineer"
              className="mt-1 block w-56 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
          </label>
          <label className="text-xs text-muted">Skills (comma-sep)
            <input value={skills} onChange={(e) => setSkills(e.target.value)} placeholder="python, aws"
              className="mt-1 block w-48 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
          </label>
          <label className="text-xs text-muted">JD (optional)
            <input value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Short description"
              className="mt-1 block w-56 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
          </label>
          <button type="submit" disabled={post.isPending} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {post.isPending ? "Posting…" : "Post job"}
          </button>
        </form>
      </SectionCard>

      <div className="mt-6">
        <SectionCard title="Open & recent jobs">
          {isLoading ? <Skeleton className="h-20" />
            : isError || !data ? <p className="text-sm text-muted">Couldn&apos;t load your jobs. <button onClick={() => refetch()} className="text-[#1B5FE8] underline">Retry</button></p>
            : data.length === 0 ? <EmptyState icon={<Briefcase size={28} />} title="No jobs yet" hint="Post your first role above." />
            : (
              <div className="divide-y divide-cardline">
                {data.map((j) => (
                  <div key={j.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-ink">{j.title}</div>
                      {j.skills && j.skills.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">{j.skills.map((s) => <span key={s} className="rounded-full bg-page px-2 py-0.5 text-[11px] text-muted">{s}</span>)}</div>
                      )}
                    </div>
                    <span className="rounded-full bg-page px-2 py-0.5 text-xs capitalize text-muted">{j.status}</span>
                  </div>
                ))}
              </div>
            )}
        </SectionCard>
      </div>
    </AppShell>
  );
}
