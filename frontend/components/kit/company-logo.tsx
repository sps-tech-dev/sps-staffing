/** SPS hexagon mark (3 verticals). variant: color | white | mono */
export function CompanyLogo({ size = 36, variant = "color" }: { size?: number; variant?: "color"|"white"|"mono" }) {
  const cA = variant === "mono" ? "#555" : variant === "white" ? "rgba(255,255,255,.95)" : "#1B5FE8";
  const cB = variant === "mono" ? "#222" : variant === "white" ? "rgba(255,255,255,.65)" : "#0D1B3E";
  const cC = variant === "mono" ? "#888" : variant === "white" ? "rgba(255,255,255,.8)" : "#E8A020";
  const d = "#ffffff";
  const ic = "rgba(255,255,255,.93)";
  const cap = variant === "color" ? "rgba(13,27,62,.85)" : ic;
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="SPS Technosoft">
      <polygon points="13.24,33 60,6 106.76,33 60,60" fill={cA} />
      <polygon points="106.76,33 106.76,87 60,114 60,60" fill={cB} />
      <polygon points="60,114 13.24,87 13.24,33 60,60" fill={cC} />
      <line x1="60" y1="60" x2="106.76" y2="33" stroke={d} strokeWidth="2.8" />
      <line x1="60" y1="60" x2="60" y2="114" stroke={d} strokeWidth="2.8" />
      <line x1="60" y1="60" x2="13.24" y2="33" stroke={d} strokeWidth="2.8" />
      <polygon points="13.24,33 60,6 106.76,33 106.76,87 60,114 13.24,87" fill="none" stroke={d} strokeWidth="2.8" />
      <circle cx="60" cy="24.5" r="5.5" fill={ic} />
      <path d="M51.5,38 C51.5,29 68.5,29 68.5,38" fill={ic} />
      <path d="M78.5,67.5 L73,73.5 L78.5,79.5" stroke={ic} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M88.5,67.5 L94,73.5 L88.5,79.5" stroke={ic} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <polygon points="36.6,67 45.5,72.5 36.6,78 27.7,72.5" fill={cap} />
    </svg>
  );
}
