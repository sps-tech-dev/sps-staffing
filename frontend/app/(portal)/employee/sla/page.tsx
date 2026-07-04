"use client";
import { AppShell } from "@/components/shell/app-shell";
import { ComingSoon } from "@/components/kit/coming-soon";

export default function Page() {
  return (
    <AppShell role="employee" title="SLA Board">
      <ComingSoon title="SLA Board" blurb="Time-to-fill and stage-ageing SLAs across your requisitions." backHref="/employee" backLabel="Back to overview" />
    </AppShell>
  );
}
