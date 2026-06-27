"use client";
import { useState } from "react";
import {
  ColumnDef, flexRender, getCoreRowModel, getSortedRowModel, SortingState, useReactTable,
} from "@tanstack/react-table";
import { Skeleton } from "@/components/kit/skeleton";
import { EmptyState } from "@/components/kit/empty-state";
import { ArrowUpDown } from "lucide-react";

interface Props<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[] | undefined;
  isLoading: boolean;
  isError: boolean;
  total: number;
  offset: number;
  limit: number;
  onOffset: (o: number) => void;
  onRetry: () => void;
  emptyTitle?: string;
}

export function AdminTable<T>({ columns, data, isLoading, isError, total, offset, limit, onOffset, onRetry, emptyTitle = "Nothing here yet" }: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const table = useReactTable({
    data: data ?? [], columns, state: { sorting }, onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(),
  });

  if (isLoading) return <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-9" />)}</div>;
  if (isError) return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <p className="text-sm text-muted">Couldn&apos;t load this list.</p>
      <button onClick={onRetry} className="rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white">Retry</button>
    </div>
  );
  if (!data || data.length === 0) return <EmptyState title={emptyTitle} />;

  const from = offset + 1, to = offset + data.length;
  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-cardline">
        <table className="w-full text-left text-sm">
          <thead className="bg-page">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th key={h.id} className="whitespace-nowrap px-3 py-2 font-semibold text-muted">
                    {h.isPlaceholder ? null : (
                      <button className="inline-flex items-center gap-1" onClick={h.column.getToggleSortingHandler()}>
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {h.column.getCanSort() && <ArrowUpDown size={12} className="opacity-50" />}
                      </button>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-t border-cardline">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="whitespace-nowrap px-3 py-2 text-ink">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between text-sm text-muted">
        <span>{from}–{to} of {total}</span>
        <div className="flex gap-2">
          <button disabled={offset === 0} onClick={() => onOffset(Math.max(0, offset - limit))}
            className="rounded-lg border border-cardline px-3 py-1 disabled:opacity-40">Prev</button>
          <button disabled={to >= total} onClick={() => onOffset(offset + limit)}
            className="rounded-lg border border-cardline px-3 py-1 disabled:opacity-40">Next</button>
        </div>
      </div>
    </div>
  );
}
