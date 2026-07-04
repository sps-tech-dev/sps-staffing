"use client";
import { AppShell } from "@/components/shell/app-shell";
import { ComingSoon } from "@/components/kit/coming-soon";

export default function Page() {
  return (
    <AppShell role="candidate" title="My Applications">
      <ComingSoon title="My Applications" blurb="Every application with its live pipeline stage." backHref="/candidate" backLabel="Back to overview" />
    </AppShell>
  );
}
