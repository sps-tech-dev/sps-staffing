"use client";
/* Academy student portal SHELL (FE surface #3) — the authenticated layout later
 * surfaces (#5 result/discount, #6 pay, #7 dashboard) live inside. Middleware
 * gates /academy/student/* by the academy cookie; this shell additionally calls
 * /auth/me so the session is proven to HOLD (a stale/absent cookie → bounce to
 * login), which is what makes reload/deep-link — not just the post-login hop —
 * actually work. */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { GraduationCap, LogOut, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";

type Me = { student_id: string; email: string; full_name: string; kind: string };

export default function StudentPortalLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "out">("loading");

  useEffect(() => {
    let alive = true;
    api<Me>("/academy/auth/me")
      .then((m) => { if (alive) { setMe(m); setState("ok"); } })
      .catch((e) => {
        if (!alive) return;
        if (e instanceof ApiError) { setState("out"); router.replace("/academy/login"); }
        else setState("out");
      });
    return () => { alive = false; };
  }, [router]);

  async function logout() {
    await api("/academy/auth/logout", { method: "POST" }).catch(() => {});
    router.replace("/academy");   // cookie cleared → back to the storefront
  }

  if (state !== "ok") {
    return (
      <div className="flex min-h-dvh items-center justify-center" style={{ background: "#F0F4FA" }}>
        <Loader2 size={22} className="animate-spin" style={{ color: "#E8A020" }} />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col" style={{ background: "#F0F4FA", color: "#0A1628" }}>
      <header className="border-b bg-white" style={{ borderColor: "#EAEEF3" }}>
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
          <Link href="/academy/student" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ background: "#FBEFD7" }}>
              <GraduationCap size={17} style={{ color: "#E8A020" }} />
            </span>
            <span className="font-extrabold" style={{ fontFamily: "'Outfit', sans-serif" }}>SPS Academy</span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="hidden text-sm sm:inline" style={{ color: "#6B7689" }}>
              Logged in as <span className="font-semibold" style={{ color: "#0A1628" }}>{me?.full_name}</span>
            </span>
            <button onClick={logout} className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold"
              style={{ background: "#F0F4FA", color: "#0A1628" }}>
              <LogOut size={14} /> Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">{children}</main>
    </div>
  );
}
