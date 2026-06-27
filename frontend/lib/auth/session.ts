export type Role = "candidate" | "client" | "employee" | "admin";
export interface Session { userId: string; role: Role; name: string; }

/** Decode the role from the auth cookie. The backend issues httpOnly JWT cookies;
 *  middleware only needs the role claim. Replace with real JWT verify in production. */
export function readSessionFromCookie(raw?: string): Session | null {
  if (!raw) return null;
  try { return JSON.parse(raw) as Session; } catch { return null; }
}

export const HOME_FOR: Record<Role, string> = {
  candidate: "/candidate", client: "/employer", employee: "/employee", admin: "/admin/dashboard",
};
