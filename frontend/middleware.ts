import { NextResponse, type NextRequest } from "next/server";
import { readSessionFromCookie, type Role } from "@/lib/auth/session";

// Unified login page (Slice 1). Role-specific login screens (/admin/login etc.)
// arrive in later slices; for now everyone authenticates at /login.
const NEED: { prefix: string; role: Role; login: string }[] = [
  { prefix: "/client", role: "client", login: "/login?role=client" },
  { prefix: "/admin", role: "admin", login: "/login?role=admin" },
  // F1: /employer/* are STAFF delivery tools (pipeline, submissions, offers,
  // invoices, vendors) — homed to the employee role. They were stranded on the
  // client role after the client-portal split (clients bounce to /client, staff
  // failed the role check -> unreachable by anyone). PENDING D4b resolved.
  { prefix: "/employer", role: "employee", login: "/login?role=employee" },
  { prefix: "/employee", role: "employee", login: "/login?role=employee" },
  { prefix: "/candidate", role: "candidate", login: "/login?role=candidate" },
  { prefix: "/privacy-rights", role: "candidate", login: "/login?role=candidate" },
];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const rule = NEED.find((r) => pathname.startsWith(r.prefix));
  if (!rule) return NextResponse.next();
  // Role is read from the httpOnly access-token JWT cookie set by the backend.
  const session = readSessionFromCookie(req.cookies.get("access_token")?.value);
  // A bound client-portal session belongs ONLY in /client — bounce it out of staff areas
  // (the backend also rejects client sessions on staff endpoints; this is the UX guard).
  if (session?.clientId && rule.prefix !== "/client") {
    const url = req.nextUrl.clone(); url.pathname = "/client"; url.search = "";
    return NextResponse.redirect(url);
  }
  if (session?.role === rule.role) return NextResponse.next();
  const url = req.nextUrl.clone();
  const [path, query] = rule.login.split("?");
  url.pathname = path; url.search = query ? `?${query}` : "";
  return NextResponse.redirect(url);
}
export const config = {
  matcher: ["/client/:path*", "/admin/:path*", "/employer/:path*", "/employee/:path*", "/candidate/:path*", "/privacy-rights/:path*"],
};
