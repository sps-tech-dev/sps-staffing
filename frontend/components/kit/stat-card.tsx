import { cn } from "@/lib/utils";
export function StatCard({ value, label, icon, accent = "#1B5FE8" }:
  { value: React.ReactNode; label: string; icon?: React.ReactNode; accent?: string }) {
  return (
    <div className={cn("flex items-center gap-4 rounded-[14px] border border-cardline bg-card p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]")}>
      {icon && (
        <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-[10px]"
             style={{ background: `${accent}18`, color: accent }}>{icon}</div>
      )}
      <div className="flex flex-col">
        <span className="font-display text-2xl font-bold leading-none text-ink">{value}</span>
        <span className="mt-1 text-xs text-muted">{label}</span>
      </div>
    </div>
  );
}
