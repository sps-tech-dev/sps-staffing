/** Small presentational primitives shared across the marketing pages. Server-safe. */
import Link from "next/link";
import type { ReactNode } from "react";

export function Eyebrow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <p className={`font-mono text-[11px] uppercase tracking-[0.3em] text-sps-sky ${className}`}>{children}</p>
  );
}

/** Section heading block: eyebrow + title + optional lead. */
export function SectionHeading({
  eyebrow, title, lead, light = false, align = "center",
}: { eyebrow?: string; title: ReactNode; lead?: ReactNode; light?: boolean; align?: "center" | "left" }) {
  const sub = light ? "text-white/65" : "text-muted";
  const head = light ? "text-white" : "text-ink";
  return (
    <div className={align === "center" ? "mx-auto max-w-2xl text-center" : "max-w-2xl text-left"}>
      {eyebrow && <Eyebrow className={align === "center" ? "" : ""}>{eyebrow}</Eyebrow>}
      <h2 className={`mt-3 font-display text-3xl font-extrabold leading-tight sm:text-4xl ${head}`}>{title}</h2>
      {lead && <p className={`mt-4 text-base leading-relaxed sm:text-lg ${sub}`}>{lead}</p>}
    </div>
  );
}

type BtnProps = { href: string; children: ReactNode; variant?: "primary" | "gold" | "ghost" | "outline"; className?: string };

const BTN: Record<NonNullable<BtnProps["variant"]>, string> = {
  primary: "bg-sps-blue text-white hover:bg-sps-blue/90 shadow-lg shadow-sps-blue/25",
  gold: "bg-sps-gold text-sps-navy hover:bg-sps-gold/90 shadow-lg shadow-sps-gold/25",
  ghost: "bg-white/10 text-white hover:bg-white/15 backdrop-blur-sm ring-1 ring-white/15",
  outline: "border border-sps-blue/30 bg-transparent text-sps-blue hover:bg-sps-blue/5",
};

export function CTAButton({ href, children, variant = "primary", className = "" }: BtnProps) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-semibold transition-all duration-200 ${BTN[variant]} ${className}`}
    >
      {children}
    </Link>
  );
}
