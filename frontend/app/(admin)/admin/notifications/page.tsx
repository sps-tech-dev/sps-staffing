"use client";
import { useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SectionCard } from "@/components/kit/section-card";
import { EmptyState } from "@/components/kit/empty-state";
import { Skeleton } from "@/components/kit/skeleton";
import { useNotifications } from "@/lib/api/hooks";
import { Bell, Info } from "lucide-react";

// F7: a READ-ONLY view of the B.10 notification LEDGER. Honesty rules:
//  - ConsoleChannel is the dev sink: status "sent" means LOGGED, not delivered.
//  - email/sms/whatsapp rows PARK (status "parked"/"pending") until Part-D
//    channels exist — shown as "awaiting channel", never as delivered.
const STATUS_STYLE: Record<string, string> = {
  sent: "bg-[#EFF6FF] text-[#1B5FE8]",       // console-logged (see banner) — not "delivered"
  pending: "bg-[#FFFBEB] text-[#D97706]",
  skipped: "bg-page text-muted",
  failed: "bg-[#FEF2F2] text-[#DC2626]",
};
const DELIVERABLE = new Set(["console"]);   // the only registered channel in dev
const STATUS_FILTERS = ["", "sent", "pending", "failed", "skipped"];

function deliveryNote(channel: string, status: string): string {
  if (channel === "console") return status === "sent" ? "logged to console (dev sink)" : "";
  // real channels aren't registered yet: a still-pending row on email/sms/whatsapp
  // is PARKED — it will not send until the Part-D channel is registered.
  if (!DELIVERABLE.has(channel) && status === "pending") return "awaiting channel (Part D) — parked";
  return "";
}

export default function NotificationsPage() {
  const [status, setStatus] = useState("");
  const { data, isLoading, isError, refetch } = useNotifications(status || undefined);
  return (
    <AppShell role="admin" title="Notification Center">
      <div className="mb-4 flex items-start gap-2 rounded-lg bg-[#EFF6FF] px-3 py-2 text-xs text-[#1B5FE8]">
        <Info size={14} className="mt-0.5 flex-shrink-0" />
        <span>
          This is the notification <strong>ledger</strong>, not a mailbox. In this environment only the
          console channel is active, so a <strong>“sent”</strong> row was written to the application log —
          it was <strong>not</strong> emailed/texted. Email, SMS and WhatsApp delivery arrive with the
          Part-D channels; those rows stay <strong>“awaiting channel.”</strong>
        </span>
      </div>

      <SectionCard title="Notifications">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {STATUS_FILTERS.map((s) => (
            <button key={s || "all"} onClick={() => setStatus(s)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${status === s ? "bg-sps-blue text-white" : "bg-page text-muted hover:text-ink"}`}>
              {s || "all"}
            </button>
          ))}
        </div>
        {isLoading ? <Skeleton className="h-32" />
          : isError || !data ? (
            <p className="text-sm text-muted">Couldn&apos;t load notifications.{" "}
              <button onClick={() => refetch()} className="text-[#1B5FE8] underline">Retry</button></p>
          ) : data.length === 0 ? (
            <EmptyState icon={<Bell size={28} />} title="No notifications"
              hint="Enqueued notifications (assessment results, interview reminders, dunning) appear here." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-cardline text-xs uppercase tracking-wide text-muted">
                    <th className="py-2 pr-3">Template</th><th className="py-2 pr-3">Channel</th>
                    <th className="py-2 pr-3">Recipient</th><th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Attempts</th><th className="py-2">When</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cardline">
                  {data.map((n) => {
                    const note = deliveryNote(n.channel_type, n.status);
                    return (
                      <tr key={n.id}>
                        <td className="py-2 pr-3 text-ink">{n.template_code}</td>
                        <td className="py-2 pr-3 text-muted">{n.channel_type}</td>
                        <td className="py-2 pr-3 font-mono text-xs text-muted">{n.recipient}</td>
                        <td className="py-2 pr-3">
                          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${STATUS_STYLE[n.status] ?? "bg-page text-muted"}`}>
                            {n.status}
                          </span>
                          {note && <p className="mt-0.5 text-[10px] text-muted">{note}</p>}
                          {n.last_error && <p className="mt-0.5 text-[10px] text-[#DC2626]">{n.last_error}</p>}
                        </td>
                        <td className="py-2 pr-3 text-muted">{n.attempts}</td>
                        <td className="py-2 text-xs text-muted">
                          {n.sent_at ? new Date(n.sent_at).toLocaleString()
                            : n.created_at ? `queued ${new Date(n.created_at).toLocaleString()}` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
      </SectionCard>
    </AppShell>
  );
}
