import { LayoutDashboard, Briefcase, Users, FileText, ClipboardList, ShieldCheck, Building2, GraduationCap, KanbanSquare, Timer } from "lucide-react";
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
  client: [
    { label: "Overview", href: "/employer", icon: LayoutDashboard },
    { label: "Jobs", href: "/employer/jobs", icon: Briefcase },
    { label: "Pipeline", href: "/employer/pipeline", icon: KanbanSquare },
    { label: "Candidates", href: "/employer/candidates", icon: Users },
  ],
  employee: [
    { label: "Overview", href: "/employee", icon: LayoutDashboard },
    { label: "Requisitions", href: "/employee/queue", icon: ClipboardList },
    { label: "SLA", href: "/employee/sla", icon: Timer },
  ],
  admin: [
    { label: "Dashboard", href: "/admin/dashboard", icon: LayoutDashboard },
    { label: "Candidates", href: "/admin/candidates", icon: Users },
    { label: "Clients", href: "/admin/clients", icon: Building2 },
    { label: "Jobs", href: "/admin/jobs", icon: Briefcase },
    { label: "Employees", href: "/admin/employees", icon: GraduationCap },
    { label: "SLA Board", href: "/admin/sla-board", icon: Timer },
    { label: "Audit Logs", href: "/admin/audit-logs", icon: FileText },
  ],
};
