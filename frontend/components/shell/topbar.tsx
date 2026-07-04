"use client";
import { useRouter } from "next/navigation";
import { Menu, Bell, LogOut } from "lucide-react";

export function Topbar({ onMenu, title }: { onMenu: () => void; title: string }) {
  const router = useRouter();
  async function signOut() {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } finally {
      router.push("/login");
      router.refresh();
    }
  }
  return (
    <header className="flex h-16 items-center justify-between border-b border-cardline bg-card px-4 lg:px-6">
      <div className="flex items-center gap-3">
        <button onClick={onMenu} className="rounded-lg p-2 hover:bg-page lg:hidden" aria-label="Menu"><Menu size={20} /></button>
        <h1 className="font-display text-lg font-bold text-ink">{title}</h1>
      </div>
      <div className="flex items-center gap-1">
        <button className="rounded-lg p-2 hover:bg-page" aria-label="Notifications"><Bell size={19} /></button>
        <button onClick={signOut} title="Sign out"
          className="inline-flex items-center gap-1.5 rounded-lg p-2 text-sm text-muted hover:bg-page hover:text-ink"
          aria-label="Sign out">
          <LogOut size={18} /><span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  );
}
