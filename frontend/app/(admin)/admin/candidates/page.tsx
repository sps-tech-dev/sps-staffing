"use client";
import { useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { AppShell } from "@/components/shell/app-shell";
import { AdminTable } from "@/components/admin/admin-table";
import { useAdminCandidates } from "@/lib/api/hooks";
import type { AdminCandidate } from "@/lib/api/types";

const columns: ColumnDef<AdminCandidate, unknown>[] = [
  { accessorKey: "full_name", header: "Name" },
  { accessorKey: "email", header: "Email", cell: ({ getValue }) => (getValue() as string) || "—" },
  { accessorKey: "phone", header: "Phone", cell: ({ getValue }) => (getValue() as string) || "—" },
  { accessorKey: "total_exp", header: "Exp (yrs)", cell: ({ getValue }) => (getValue() ?? "—") as string },
];

export default function AdminCandidatesPage() {
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState("");
  const query = useAdminCandidates(offset, q);
  return (
    <AppShell role="admin" title="Candidates">
      <input
        value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }}
        placeholder="Search by name…"
        className="mb-4 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8] sm:max-w-xs"
      />
      <AdminTable columns={columns} data={query.data?.items} isLoading={query.isLoading} isError={query.isError}
        total={query.data?.total ?? 0} offset={offset} limit={20} onOffset={setOffset} onRetry={query.refetch}
        emptyTitle="No candidates yet" />
    </AppShell>
  );
}
