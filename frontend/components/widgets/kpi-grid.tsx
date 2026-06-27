import { StatCard } from "@/components/kit/stat-card";
export function KpiGrid({ items }:
  { items: { value: React.ReactNode; label: string; icon?: React.ReactNode; accent?: string }[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((it, i) => <StatCard key={i} {...it} />)}
    </div>
  );
}
