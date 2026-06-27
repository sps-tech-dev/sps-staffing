/** Typed fetch wrapper: sends cookies, adds Idempotency-Key on writes,
 *  normalizes the canonical error envelope (Master Architecture Part 31). */
export class ApiError extends Error {
  constructor(public code: string, message: string, public details?: unknown) { super(message); }
}
const WRITE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (WRITE.has(method)) headers.set("Idempotency-Key", crypto.randomUUID());

  const res = await fetch(`/api${path}`, { ...init, method, headers, credentials: "include" });
  if (res.status === 401) {
    // silent refresh then retry once
    await fetch("/api/auth/refresh", { method: "POST", credentials: "include" }).catch(() => {});
    const retry = await fetch(`/api${path}`, { ...init, method, headers, credentials: "include" });
    if (!retry.ok) throw await toError(retry);
    return retry.json();
  }
  if (!res.ok) throw await toError(res);
  return res.json();
}
async function toError(res: Response) {
  try { const b = await res.json(); const e = b?.error ?? {}; return new ApiError(e.code ?? "ERROR", e.message ?? res.statusText, e.details); }
  catch { return new ApiError("ERROR", res.statusText); }
}
