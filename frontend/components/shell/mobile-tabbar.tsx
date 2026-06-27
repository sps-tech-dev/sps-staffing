"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV } from "@/lib/nav";
import type { Role } from "@/lib/auth/session";
import { cn } from "@/lib/utils";
export function MobileTabBar({ role }: { role: Role }) {
  const pathname = usePathname();
  const items = (NAV[role] ?? []).slice(0, 4);
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-cardline bg-card md:hidden">
      {items.map((it) => {
        const active = pathname === it.href || pathname.startsWith(it.href + "/");
        const Icon = it.icon;
        return (
          <Link key={it.href} href={it.href}
            className={cn("flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px]",
              active ? "text-sps-blue" : "text-muted")}>
            <Icon size={20} /><span>{it.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
