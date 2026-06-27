export function ProgressRing({ value, max = 100, size = 64, stroke = 7, color = "#1B5FE8", label }:
  { value: number; max?: number; size?: number; stroke?: number; color?: string; label?: string }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, pct = Math.min(value / max, 1);
  return (
    <div className="inline-flex flex-col items-center gap-1">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#EAEEF3" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
                strokeDasharray={c} strokeDashoffset={c*(1-pct)} strokeLinecap="round" />
      </svg>
      <span className="text-xs font-semibold text-ink">{label ?? `${Math.round(pct*100)}%`}</span>
    </div>
  );
}
