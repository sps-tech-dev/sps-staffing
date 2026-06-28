"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import {
  useClientMe, useClientTeam, useClientAddTeammate, useClientJobs, useClientReassignJob,
} from "@/lib/api/hooks";
import { Users, ShieldCheck } from "lucide-react";

const ROLE_LABEL: Record<string, string> = { client_admin: "HR / Admin", client_manager: "Hiring manager" };

function AddTeammate() {
  const add = useClientAddTeammate();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [pw, setPw] = useState("");
  const [role, setRole] = useState<"client_admin" | "client_manager">("client_manager");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null); setOk(false);
    add.mutate({ email: email.trim(), full_name: name.trim(), initial_password: pw, role }, {
      onSuccess: () => { setOk(true); setEmail(""); setName(""); setPw(""); setRole("client_manager"); },
      onError: (er) => setErr((er as { message?: string }).message ?? "Couldn't add the teammate."),
    });
  }
  return (
    <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2" noValidate>
      <label className="text-xs text-muted">Name
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Priya Sharma"
          className="mt-1 block w-44 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
      </label>
      <label className="text-xs text-muted">Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="priya@company.com"
          className="mt-1 block w-52 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
      </label>
      <label className="text-xs text-muted">Temp password
        <input type="text" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="Set initial password"
          className="mt-1 block w-44 rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]" />
      </label>
      <label className="text-xs text-muted">Role
        <select value={role} onChange={(e) => setRole(e.target.value as "client_admin" | "client_manager")}
          className="mt-1 block rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]">
          <option value="client_manager">Hiring manager</option>
          <option value="client_admin">HR / Admin</option>
        </select>
      </label>
      <button type="submit" disabled={add.isPending}
        className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
        {add.isPending ? "Adding…" : "Add teammate"}
      </button>
      {ok && <span className="text-xs text-[#059669]">Teammate added.</span>}
      {err && <span role="alert" className="text-xs text-[#DC2626]">{err}</span>}
    </form>
  );
}

function ReassignJobs() {
  const jobs = useClientJobs();
  const team = useClientTeam();
  const reassign = useClientReassignJob();
  const [sel, setSel] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const managers = (team.data ?? []);

  if (jobs.isLoading) return <Skeleton className="h-20" />;
  if (jobs.isError || !jobs.data) return <p className="text-sm text-muted">Couldn&apos;t load jobs.</p>;
  if (jobs.data.length === 0) return <EmptyState icon={<Users size={26} />} title="No jobs to reassign" hint="Posted jobs show up here." />;

  return (
    <div className="divide-y divide-cardline">
      {jobs.data.map((j) => (
        <div key={j.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
          <div className="text-sm font-medium text-ink">{j.title}</div>
          <div className="flex items-center gap-2">
            <select value={sel[j.id] ?? ""} onChange={(e) => setSel((s) => ({ ...s, [j.id]: e.target.value }))}
              className="rounded-lg border border-cardline bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-[#1B5FE8]">
              <option value="">Reassign to…</option>
              {managers.map((m) => <option key={m.user_id} value={m.user_id}>{m.name ?? m.email} ({ROLE_LABEL[m.role]})</option>)}
            </select>
            <button disabled={!sel[j.id] || reassign.isPending}
              onClick={() => { setMsg(null); reassign.mutate({ jobId: j.id, owner_user_id: sel[j.id] }, {
                onSuccess: () => setMsg(`Reassigned “${j.title}”.`),
                onError: (er) => setMsg((er as { message?: string }).message ?? "Couldn't reassign."),
              }); }}
              className="rounded-lg border border-cardline px-3 py-1.5 text-sm font-medium text-ink disabled:opacity-50">
              Reassign
            </button>
          </div>
        </div>
      ))}
      {msg && <p className="pt-2 text-xs text-muted">{msg}</p>}
    </div>
  );
}

export default function ClientTeamPage() {
  const me = useClientMe();
  const team = useClientTeam();
  const isHR = me.data?.client_role === "client_admin";

  if (me.isLoading) return <AppShell role="client" title="Team"><Skeleton className="h-24" /></AppShell>;

  if (!isHR) {
    return (
      <AppShell role="client" title="Team">
        <SectionCard title="Team management">
          <EmptyState icon={<ShieldCheck size={28} />} title="HR access only"
            hint="Only your HR / admin can manage teammates and reassign jobs." />
        </SectionCard>
      </AppShell>
    );
  }

  return (
    <AppShell role="client" title="Team">
      <SectionCard title="Invite a teammate">
        <p className="mb-3 text-xs text-muted">Hiring managers see only their own jobs&apos; pipeline; HR (you) sees everything and manages offers.</p>
        <AddTeammate />
      </SectionCard>

      <div className="mt-6">
        <SectionCard title="Your team">
          {team.isLoading ? <Skeleton className="h-20" />
            : team.isError || !team.data ? <p className="text-sm text-muted">Couldn&apos;t load the team.</p>
            : (
              <div className="divide-y divide-cardline">
                {team.data.map((m) => (
                  <div key={m.user_id} className="flex items-center justify-between gap-2 py-2.5">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-ink">{m.name ?? m.email}{m.is_self && <span className="ml-1 text-xs text-muted">(you)</span>}</div>
                      <div className="text-xs text-muted">{m.email}</div>
                    </div>
                    <span className="rounded-full bg-page px-2 py-0.5 text-xs text-muted">{ROLE_LABEL[m.role]}</span>
                  </div>
                ))}
              </div>
            )}
        </SectionCard>
      </div>

      <div className="mt-6">
        <SectionCard title="Reassign jobs">
          <p className="mb-3 text-xs text-muted">Move a job (and its whole pipeline) to a different hiring manager.</p>
          <ReassignJobs />
        </SectionCard>
      </div>
    </AppShell>
  );
}
