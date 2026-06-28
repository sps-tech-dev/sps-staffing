/** Corporate marketing footer — company brief, nav, contact, copyright. No login. */
import Link from "next/link";
import { Mail, MapPin, Phone } from "lucide-react";
import { CompanyLogo } from "@/components/kit/company-logo";

const NAV = [
  { label: "Home", href: "/" },
  { label: "About", href: "/about" },
  { label: "Services", href: "/services" },
  { label: "Career", href: "/career" },
  { label: "Contact", href: "/contact" },
];
const VERTICALS = [
  { label: "Staffing & Recruitment", href: "/staffing-and-recruitment" },
  { label: "Academy / Training", href: "/academy" },
  { label: "IT Consulting", href: "/consulting" },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-white/10 bg-sps-navy text-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-14 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-1">
          <Link href="/" className="flex items-center gap-2.5">
            <CompanyLogo size={32} />
            <span className="font-display text-sm font-bold tracking-tight">
              SPS<span className="text-sps-sky">Technosoft</span>
            </span>
          </Link>
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-white/55">
            A multi-vertical technology company — staffing &amp; recruitment, training, and IT
            consulting — built on one engineering-grade talent platform.
          </p>
        </div>

        <nav className="text-sm" aria-label="Footer">
          <h3 className="font-display text-xs font-semibold uppercase tracking-wider text-white/40">Company</h3>
          <ul className="mt-4 space-y-2.5">
            {NAV.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-white/65 transition-colors hover:text-white">{l.label}</Link>
              </li>
            ))}
          </ul>
        </nav>

        <nav className="text-sm" aria-label="Verticals">
          <h3 className="font-display text-xs font-semibold uppercase tracking-wider text-white/40">What we do</h3>
          <ul className="mt-4 space-y-2.5">
            {VERTICALS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-white/65 transition-colors hover:text-white">{l.label}</Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="text-sm">
          <h3 className="font-display text-xs font-semibold uppercase tracking-wider text-white/40">Contact</h3>
          <ul className="mt-4 space-y-3 text-white/65">
            <li className="flex items-start gap-2.5">
              <MapPin size={16} className="mt-0.5 shrink-0 text-sps-sky" aria-hidden />
              <span>Vadodara, Gujarat, India</span>
            </li>
            <li className="flex items-center gap-2.5">
              <Mail size={16} className="shrink-0 text-sps-sky" aria-hidden />
              <a href="mailto:hello@spstechnosoft.com" className="hover:text-white">hello@spstechnosoft.com</a>
            </li>
            <li className="flex items-center gap-2.5">
              <Phone size={16} className="shrink-0 text-sps-sky" aria-hidden />
              <span>+91 — coming soon</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-white/10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-6 py-6 text-xs text-white/40 sm:flex-row">
          <p>© {2026} SPS Technosoft Pvt Ltd. All rights reserved.</p>
          <p className="font-mono uppercase tracking-[0.2em]">Staffing · Training · Consulting</p>
        </div>
      </div>
    </footer>
  );
}
