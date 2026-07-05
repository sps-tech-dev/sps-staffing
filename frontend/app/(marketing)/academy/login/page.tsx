"use client";
/* Academy STUDENT login (FE surface #3) — A3 two-auth: sets the SEPARATE
 * academy_access_token cookie (distinct secret from staff). On success, lands in
 * the student portal via the backend's `home`. */
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api/client";
import { StorefrontShell } from "../_lib";

const GOLD = "#E8A020";
const inputCls = "w-full rounded-xl border bg-white px-3.5 py-2.5 text-sm outline-none focus:border-[#E8A020]";
const inputStyle = { borderColor: "#DDE3EC", color: "#0A1628" } as const;

export default function AcademyLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await api<{ home?: string; full_name?: string }>(
        "/academy/auth/login",
        { method: "POST", body: JSON.stringify({ email, password }) });
      router.push(res.home ?? "/academy/student");   // cookie is set; land in the portal
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed. Please try again.");
      setBusy(false);
    }
  }

  return (
    <StorefrontShell title="Student login" eyebrow="Training & Internships">
      <form onSubmit={onSubmit} className="mx-auto max-w-md rounded-2xl bg-white p-8" style={{ border: "1px solid #EAEEF3" }}>
        <label className="block">
          <span className="mb-1 block text-sm font-semibold" style={{ color: "#0A1628" }}>Email</span>
          <input type="email" className={inputCls} style={inputStyle} value={email}
            onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        </label>
        <label className="mt-4 block">
          <span className="mb-1 block text-sm font-semibold" style={{ color: "#0A1628" }}>Password</span>
          <input type="password" className={inputCls} style={inputStyle} value={password}
            onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </label>

        {error && (
          <div className="mt-5 rounded-xl px-4 py-3 text-sm" style={{ background: "#FEF2F2", color: "#B91C1C", border: "1px solid #FECACA" }}>
            {error}
          </div>
        )}

        <button type="submit" disabled={busy}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold disabled:opacity-60"
          style={{ background: GOLD, color: "#0A1628" }}>
          {busy && <Loader2 size={16} className="animate-spin" />}
          {busy ? "Signing in…" : "Log in"}
        </button>
        <p className="mt-3 text-center text-xs" style={{ color: "#9AA6BC" }}>
          New here? <Link href="/academy" className="font-semibold" style={{ color: GOLD }}>Browse courses</Link> and apply.
        </p>
      </form>
    </StorefrontShell>
  );
}
