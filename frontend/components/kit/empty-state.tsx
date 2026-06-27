export function EmptyState({ title, hint, icon }:
  { title: string; hint?: string; icon?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-center">
      {icon && <div className="text-sps-slate">{icon}</div>}
      <p className="font-display font-semibold text-ink">{title}</p>
      {hint && <p className="max-w-xs text-sm text-muted">{hint}</p>}
    </div>
  );
}
