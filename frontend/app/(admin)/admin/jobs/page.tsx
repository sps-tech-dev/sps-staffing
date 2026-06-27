"use client";
import { useState } from "react";
import { ColumnDef } from "@tanstack/react-table";
import { AppShell } from "@/components/shell/app-shell";
import { AdminTable } from "@/components/admin/admin-table";
import { useAdminJobs } from "@/lib/api/hooks";
import type { AdminJobRow } from "@/lib/api/types";

const columns: ColumnDef<AdminJobRow, unknown>[] = [
  { accessorKey: "title", header: "Title" },
  { accessorKey: "status", header: "Status" },
];

export default function AdminJobsPage() {
  const [offset, setOffset] = useState(0);
  const query = useAdminJobs(offset);
  return (
    <AppShell role="admin" title="Jobs">
      <AdminTable columns={columns} data={query.data?.items} isLoading={query.isLoading} isError={query.isError}
        total={query.data?.total ?? 0} offset={offset} limit={20} onOffset={setOffset} onRetry={query.refetch}
        emptyTitle="No jobs yet" />
    </AppShell>
  );
}
