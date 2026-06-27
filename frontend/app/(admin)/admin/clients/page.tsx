"use client";
import { useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { AppShell } from "@/components/shell/app-shell";
import { AdminTable } from "@/components/admin/admin-table";
import { useAdminClients } from "@/lib/api/hooks";
import type { AdminClient } from "@/lib/api/types";

const columns: ColumnDef<AdminClient, unknown>[] = [
  { accessorKey: "name", header: "Client" },
  { accessorKey: "industry", header: "Industry", cell: ({ getValue }) => (getValue() as string) || "—" },
  { accessorKey: "status", header: "Status" },
];

export default function AdminClientsPage() {
  const [offset, setOffset] = useState(0);
  const query = useAdminClients(offset);
  return (
    <AppShell role="admin" title="Clients">
      <AdminTable columns={columns} data={query.data?.items} isLoading={query.isLoading} isError={query.isError}
        total={query.data?.total ?? 0} offset={offset} limit={20} onOffset={setOffset} onRetry={query.refetch}
        emptyTitle="No clients yet" />
    </AppShell>
  );
}
