import { NextResponse, type NextRequest } from "next/server";
import { readSessionFromCookie, HOME_FOR, type Role } from "@/lib/auth/session";

const NEED: { prefix: string; role: Role; login: string }[] = [
  { prefix: "/admin", role: "admin", login: "/admin/login" },
  { prefix: "/employer", role: "client", login: "/login?role=client" },
  { prefix: "/employee", role: "employee", login: "/employee/login" },
  { prefix: "/candidate", role: "candidate", login: "/login?role=candidate" },
  { prefix: "/privacy-rights", role: "candidate", login: "/login?role=candidate" },
];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const rule = NEED.find((r) => pathname.startsWith(r.prefix));
  if (!rule) return NextResponse.next();
  const session = readSessionFromCookie(req.cookies.get("sps_session")?.value);
  if (session?.role === rule.role) return NextResponse.next();
  const url = req.nextUrl.clone();
  const [path, query] = rule.login.split("?");
  url.pathname = path; url.search = query ? `?${query}` : "";
  return NextResponse.redirect(url);
}
export const config = {
  matcher: ["/admin/:path*", "/employer/:path*", "/employee/:path*", "/candidate/:path*", "/privacy-rights/:path*"],
};
