"use client";

import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";

/** Minimal admin landing (Slice 1) — gives the owner/admin a real page to land on
 *  after login. The full admin console (TanStack tables: candidates/clients/jobs/
 *  audit) is a later slice (F4). */
export default function AdminDashboard() {
  return (
    <AppShell role="admin" title="Admin">
      <SectionCard title="Welcome">
        <p className="text-sm text-ink">
          You are signed in as an owner/admin of SPS Technosoft.
        </p>
        <p className="mt-2 text-sm text-muted">
          The full admin console (candidates, clients, jobs, audit logs) ships in a
          later slice. Authentication, tenant isolation, and routing are live.
        </p>
      </SectionCard>
    </AppShell>
  );
}
