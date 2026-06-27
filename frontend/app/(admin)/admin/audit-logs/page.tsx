"use client";
import { useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { AppShell } from "@/components/shell/app-shell";
import { AdminTable } from "@/components/admin/admin-table";
import { useAdminAuditLogs } from "@/lib/api/hooks";
import type { AuditRow } from "@/lib/api/types";

const columns: ColumnDef<AuditRow, unknown>[] = [
  { accessorKey: "ts", header: "When", cell: ({ getValue }) => {
      const v = getValue() as string | null;
      return v ? new Date(v).toLocaleString() : "—";
    } },
  { accessorKey: "action", header: "Action" },
  { accessorKey: "entity", header: "Entity" },
  { accessorKey: "entity_id", header: "Entity ID", cell: ({ getValue }) => {
      const v = getValue() as string | null;
      return v ? `${v.slice(0, 8)}…` : "—";
    } },
];

export default function AdminAuditLogsPage() {
  const [offset, setOffset] = useState(0);
  const query = useAdminAuditLogs(offset);
  return (
    <AppShell role="admin" title="Audit Logs">
      <p className="mb-3 text-xs text-muted">
        Append-only audit trail (convention-enforced; a restricted INSERT-only DB role is pending).
      </p>
      <AdminTable columns={columns} data={query.data?.items} isLoading={query.isLoading} isError={query.isError}
        total={query.data?.total ?? 0} offset={offset} limit={50} onOffset={setOffset} onRetry={query.refetch}
        emptyTitle="No audit events yet" />
    </AppShell>
  );
}
