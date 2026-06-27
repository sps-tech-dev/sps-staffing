export type Role = "candidate" | "client" | "employee" | "admin";
export interface Session {
  userId: string;
  role: Role;
  name: string;
  tenantId?: string;
}

/** Edge-safe base64url-decode of a JWT payload (no signature verify — that's the
 *  backend's job on every API call; the edge only needs the role/tenant for routing). */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64.padEnd(b64.length + ((4 - (b64.length % 4)) % 4), "=");
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

/** Decode the role from the httpOnly access-token JWT cookie. The backend issues
 *  it on login; middleware reads it server-side (httpOnly is fine on the server). */
export function readSessionFromCookie(token?: string): Session | null {
  if (!token) return null;
  const p = decodeJwtPayload(token);
  if (!p || typeof p.role !== "string") return null;
  if (typeof p.exp === "number" && Math.floor(Date.now() / 1000) >= p.exp) return null; // expired
  return {
    userId: String(p.sub ?? ""),
    role: p.role as Role,
    name: typeof p.name === "string" ? p.name : "",
    tenantId: typeof p.tenant_id === "string" ? p.tenant_id : undefined,
  };
}

export const HOME_FOR: Record<Role, string> = {
  candidate: "/candidate",
  client: "/employer",
  employee: "/employee",
  admin: "/admin/dashboard",
};
