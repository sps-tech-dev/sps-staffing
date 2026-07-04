"use client";
import { AppShell } from "@/components/shell/app-shell";
import { ComingSoon } from "@/components/kit/coming-soon";

export default function Page() {
  return (
    <AppShell role="admin" title="Employees">
      <ComingSoon title="Employees" blurb="Staff roster, roles and access management." backHref="/admin/dashboard" backLabel="Back to dashboard" />
    </AppShell>
  );
}
