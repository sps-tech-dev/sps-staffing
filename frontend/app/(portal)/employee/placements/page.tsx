"use client";
import { AppShell } from "@/components/shell/app-shell";
import { ComingSoon } from "@/components/kit/coming-soon";

export default function Page() {
  return (
    <AppShell role="employee" title="Placements & Invoices">
      <ComingSoon title="Placements & Invoices" blurb="Placements, guarantee windows, invoices and commissions." backHref="/employee" backLabel="Back to overview" />
    </AppShell>
  );
}
