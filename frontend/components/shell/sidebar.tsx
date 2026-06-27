"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CompanyLogo } from "@/components/kit/company-logo";
import { NAV } from "@/lib/nav";
import type { Role } from "@/lib/auth/session";
import { cn } from "@/lib/utils";

export function Sidebar({ role, collapsed }: { role: Role; collapsed: boolean }) {
  const pathname = usePathname();
  const items = NAV[role] ?? [];
  return (
    <nav className={cn("flex h-full flex-col bg-sidebar text-white/85 transition-all", collapsed ? "w-[72px]" : "w-60")}>
      <div className="flex h-16 items-center gap-2 px-4">
        <CompanyLogo size={32} />
        {!collapsed && <span className="font-display text-sm font-extrabold text-white">SPS<span className="text-sps-sky">Technosoft</span></span>}
      </div>
      <ul className="mt-2 flex-1 space-y-1 px-2">
        {items.map((it) => {
          const active = pathname === it.href || pathname.startsWith(it.href + "/");
          const Icon = it.icon;
          return (
            <li key={it.href}>
              <Link href={it.href} title={it.label}
                className={cn("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition",
                  active ? "bg-sps-blue text-white" : "hover:bg-white/8")}>
                <Icon size={18} className="flex-shrink-0" />
                {!collapsed && <span>{it.label}</span>}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
