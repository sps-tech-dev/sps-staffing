import { LayoutDashboard, Briefcase, Users, FileText, ClipboardList, ShieldCheck, Building2, GraduationCap, KanbanSquare, Timer, Send, FileSignature, CalendarClock, Receipt } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Role } from "./auth/session";

export interface NavItem { label: string; href: string; icon: LucideIcon; }

export const NAV: Record<Role, NavItem[]> = {
  candidate: [
    { label: "Overview", href: "/candidate", icon: LayoutDashboard },
    { label: "Jobs", href: "/candidate/jobs", icon: Briefcase },
    { label: "Applications", href: "/candidate/applications", icon: ClipboardList },
    { label: "Privacy", href: "/privacy-rights", icon: ShieldCheck },
  ],
  // External client self-service portal (role `client` + bound client_id). Strictly
  // scoped to the client's own company; the legacy /employer/* staff tools are no
  // longer linked from here.
  client: [
    { label: "Overview", href: "/client", icon: LayoutDashboard },
    { label: "Jobs", href: "/client/jobs", icon: Briefcase },
    { label: "Pipeline", href: "/client/pipeline", icon: KanbanSquare },
    { label: "Submissions", href: "/client/submissions", icon: Send },
    { label: "Interviews", href: "/client/interviews", icon: CalendarClock },
    { label: "Offers", href: "/client/offers", icon: FileSignature },
    { label: "Team", href: "/client/team", icon: Users },
  ],
  employee: [
    { label: "Overview", href: "/employee", icon: LayoutDashboard },
    { label: "Requisitions", href: "/employee/queue", icon: ClipboardList },
    { label: "SLA", href: "/employee/sla", icon: Timer },
    // F1: the staff delivery tools (re-homed from the stranded client role)
    { label: "Pipeline", href: "/employer/pipeline", icon: KanbanSquare },
    { label: "Jobs", href: "/employer/jobs", icon: Briefcase },
    { label: "Submissions", href: "/employer/submissions", icon: Send },
    { label: "Interviews", href: "/employer/interviews", icon: CalendarClock },
    { label: "Offers", href: "/employer/offers", icon: FileSignature },
    { label: "Invoices", href: "/employer/invoices", icon: Receipt },
    { label: "Vendors", href: "/employer/vendors", icon: Building2 },
    // F1: upcoming deep screens (ComingSoon placeholders until their slice)
    { label: "Assessments", href: "/employee/assessments", icon: GraduationCap },
    { label: "Placements", href: "/employee/placements", icon: Users },
    { label: "CRM", href: "/employee/crm", icon: FileText },
  ],
  admin: [
    { label: "Dashboard", href: "/admin/dashboard", icon: LayoutDashboard },
    { label: "Candidates", href: "/admin/candidates", icon: Users },
    { label: "Clients", href: "/admin/clients", icon: Building2 },
    { label: "Client Sign-ups", href: "/admin/client-registrations", icon: Building2 },
    { label: "Jobs", href: "/admin/jobs", icon: Briefcase },
    { label: "Employees", href: "/admin/employees", icon: GraduationCap },
    { label: "SLA Board", href: "/admin/sla-board", icon: Timer },
    { label: "Audit Logs", href: "/admin/audit-logs", icon: FileText },
  ],
};
