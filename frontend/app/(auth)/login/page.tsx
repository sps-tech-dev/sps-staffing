"use client";

import { Suspense, useState } from "react";
import { useRouter } from "next/navigation";
import { loginSchema } from "@/lib/validation";

function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const parsed = loginSchema.safeParse({ email, password });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Please check your input");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(parsed.data),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(body?.error?.message ?? "Login failed");
        return;
      }
      router.push(body.home ?? "/");
      router.refresh();
    } catch {
      setError("Network error — please try again");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-page px-4">
      <div className="w-full max-w-sm rounded-2xl border border-cardline bg-card p-6 shadow-sm sm:p-8">
        <h1 className="text-xl font-semibold text-ink">Sign in to SPS Technosoft</h1>
        <p className="mt-1 text-sm text-muted">Use your work email and password.</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-ink">Email</label>
            <input
              id="email" type="email" autoComplete="email" value={email} autoFocus
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]"
              placeholder="name@example.com"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-ink">Password</label>
            <input
              id="password" type="password" autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-cardline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-[#1B5FE8]"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p role="alert" className="rounded-lg bg-[#FEF2F2] px-3 py-2 text-sm text-[#DC2626]">{error}</p>
          )}

          <button
            type="submit" disabled={loading}
            className="w-full rounded-lg bg-[#1B5FE8] px-4 py-2 text-sm font-semibold text-white transition disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-muted">
          New candidate?{" "}
          <a href="/register" className="font-medium text-[#1B5FE8] hover:underline">Create your profile</a>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
