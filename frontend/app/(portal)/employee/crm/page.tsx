"use client";
import { AppShell } from "@/components/shell/app-shell";
import { ComingSoon } from "@/components/kit/coming-soon";

export default function Page() {
  return (
    <AppShell role="employee" title="CRM & Leads">
      <ComingSoon title="CRM & Leads" blurb="The BD lead board: stages, activities and convert-to-client." backHref="/employee" backLabel="Back to overview" />
    </AppShell>
  );
}
