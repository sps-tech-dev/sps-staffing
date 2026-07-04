"use client";
import { AppShell } from "@/components/shell/app-shell";
import { ComingSoon } from "@/components/kit/coming-soon";

export default function Page() {
  return (
    <AppShell role="employee" title="Assessments">
      <ComingSoon title="Assessments" blurb="Issue aptitude tests, track results and waivers from one queue." backHref="/employee" backLabel="Back to overview" />
    </AppShell>
  );
}
