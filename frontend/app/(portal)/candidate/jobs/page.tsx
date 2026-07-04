"use client";
import { AppShell } from "@/components/shell/app-shell";
import { ComingSoon } from "@/components/kit/coming-soon";

export default function Page() {
  return (
    <AppShell role="candidate" title="Browse Jobs">
      <ComingSoon title="Browse Jobs" blurb="Open roles matched to your profile appear here." backHref="/candidate" backLabel="Back to overview" />
    </AppShell>
  );
}
