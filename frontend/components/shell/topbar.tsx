"use client";
import { Menu, Bell, UserCircle2 } from "lucide-react";
export function Topbar({ onMenu, title }: { onMenu: () => void; title: string }) {
  return (
    <header className="flex h-16 items-center justify-between border-b border-cardline bg-card px-4 lg:px-6">
      <div className="flex items-center gap-3">
        <button onClick={onMenu} className="rounded-lg p-2 hover:bg-page lg:hidden" aria-label="Menu"><Menu size={20} /></button>
        <h1 className="font-display text-lg font-bold text-ink">{title}</h1>
      </div>
      <div className="flex items-center gap-1">
        <button className="rounded-lg p-2 hover:bg-page" aria-label="Notifications"><Bell size={19} /></button>
        <button className="rounded-lg p-2 hover:bg-page" aria-label="Account"><UserCircle2 size={22} /></button>
      </div>
    </header>
  );
}
