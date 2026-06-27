"use client";
import { useState } from "react";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { MobileTabBar } from "./mobile-tabbar";
import type { Role } from "@/lib/auth/session";
import { cn } from "@/lib/utils";

/** Responsive shell:
 *  desktop (lg+): full sidebar + topbar
 *  tablet (md):   icon-rail sidebar (toggle to expand)
 *  mobile (<md):  hidden sidebar → drawer + bottom tab bar  */
export function AppShell({ role, title, children }:
  { role: Role; title: string; children: React.ReactNode }) {
  const [drawer, setDrawer] = useState(false);     // mobile overlay
  const [collapsed, setCollapsed] = useState(true); // md rail default
  return (
    <div className="flex min-h-dvh bg-page">
      {/* static sidebar md+ */}
      <div className="hidden md:block" onMouseEnter={() => setCollapsed(false)} onMouseLeave={() => setCollapsed(true)}>
        <div className="sticky top-0 h-dvh"><Sidebar role={role} collapsed={collapsed} /></div>
      </div>
      {/* mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
          <div className="absolute left-0 top-0 h-full"><Sidebar role={role} collapsed={false} /></div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title={title} onMenu={() => setDrawer(true)} />
        <main className={cn("mx-auto w-full max-w-screen-2xl flex-1 p-4 pb-24 md:p-6 md:pb-6")}>{children}</main>
      </div>
      <MobileTabBar role={role} />
    </div>
  );
}
