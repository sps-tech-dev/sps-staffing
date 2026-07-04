"use client";
import { AppShell } from "@/components/shell/app-shell";
import { ComingSoon } from "@/components/kit/coming-soon";

export default function Page() {
  return (
    <AppShell role="admin" title="SLA Board">
      <ComingSoon title="SLA Board" blurb="Org-wide SLA health across recruiters and requisitions." backHref="/admin/dashboard" backLabel="Back to dashboard" />
    </AppShell>
  );
}
