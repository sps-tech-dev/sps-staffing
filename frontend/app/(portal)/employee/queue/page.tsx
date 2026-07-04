"use client";
import { AppShell } from "@/components/shell/app-shell";
import { ComingSoon } from "@/components/kit/coming-soon";

export default function Page() {
  return (
    <AppShell role="employee" title="Requisition Queue">
      <ComingSoon title="Requisition Queue" blurb="Prioritised requisitions with SLA countdowns land here." backHref="/employee" backLabel="Back to overview" />
    </AppShell>
  );
}
