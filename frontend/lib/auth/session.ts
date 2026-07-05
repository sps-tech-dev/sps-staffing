export type Role = "candidate" | "client" | "employee" | "admin";
export interface Session {
  userId: string;
  role: Role;
  name: string;
  tenantId?: string;
  clientId?: string;   // set ONLY for a bound client-portal session (nested client scope)
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
    clientId: typeof p.client_id === "string" ? p.client_id : undefined,
  };
}

/** A3 two-auth: the academy STUDENT session — a SEPARATE cookie
 *  (academy_access_token) signed with a DISTINCT secret from the staff
 *  access_token. Reject anything that isn't an academy-student token: a staff
 *  token has type="access" (not "academy_access") and no kind, so even if it were
 *  placed in this cookie it fails here — defense-in-depth over the distinct name;
 *  the backend's separate secret is the cryptographic boundary. */
export interface AcademySession { studentId: string; email: string; }
export function readAcademySessionFromCookie(token?: string): AcademySession | null {
  if (!token) return null;
  const p = decodeJwtPayload(token);
  if (!p) return null;
  if (p.kind !== "academy_student" || p.type !== "academy_access") return null;
  if (typeof p.exp === "number" && Math.floor(Date.now() / 1000) >= p.exp) return null; // expired
  return { studentId: String(p.sub ?? ""), email: typeof p.email === "string" ? p.email : "" };
}

export const HOME_FOR: Record<Role, string> = {
  candidate: "/candidate",
  client: "/client",
  employee: "/employee",
  admin: "/admin/dashboard",
};
