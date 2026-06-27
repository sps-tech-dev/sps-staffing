const MAP: Record<string, { bg: string; fg: string }> = {
  applied:{bg:"#EFF6FF",fg:"#2563EB"}, screening:{bg:"#FFFBEB",fg:"#D97706"},
  interview:{bg:"#EFF6FF",fg:"#2563EB"}, scheduled:{bg:"#EFF6FF",fg:"#2563EB"},
  selected:{bg:"#F0FDF4",fg:"#16A34A"}, completed:{bg:"#F0FDF4",fg:"#16A34A"},
  joined:{bg:"#F0FDF4",fg:"#16A34A"}, offer:{bg:"#ECFDF5",fg:"#059669"},
  rejected:{bg:"#FEF2F2",fg:"#DC2626"}, cancelled:{bg:"#FEF2F2",fg:"#DC2626"},
  withdrawn:{bg:"#F9FAFB",fg:"#6B7280"}, neutral:{bg:"#F9FAFB",fg:"#6B7280"},
  active:{bg:"#F0FDF4",fg:"#16A34A"}, paused:{bg:"#FFFBEB",fg:"#D97706"}, closed:{bg:"#FEF2F2",fg:"#DC2626"},
};
export function StatusPill({ status }: { status: string }) {
  const c = MAP[status?.toLowerCase()] ?? MAP.neutral;
  return (
    <span className="inline-block rounded-full px-3 py-1 text-[11px] font-semibold capitalize"
          style={{ background: c.bg, color: c.fg }} aria-label={`Status: ${status}`}>{status}</span>
  );
}
