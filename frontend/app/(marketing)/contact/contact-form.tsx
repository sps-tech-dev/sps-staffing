"use client";
/** Contact form — STUB submit. No email/backend infra yet (tracked in PENDING).
 *  Validates client-side, then shows a success state WITHOUT sending anything.
 *  TODO: wire to a real contact endpoint / email service before launch. */
import { useState } from "react";
import { CheckCircle2, Send } from "lucide-react";

type Status = "idle" | "submitting" | "done";

export function ContactForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [form, setForm] = useState({ name: "", email: "", subject: "", message: "" });
  const [error, setError] = useState<string | null>(null);

  function update(k: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.name.trim() || !form.email.trim() || !form.message.trim()) {
      setError("Please fill in your name, email, and message.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      setError("Please enter a valid email address.");
      return;
    }
    // STUB: no network call — email infra is not yet provisioned (see PENDING / E1).
    setStatus("submitting");
    setTimeout(() => setStatus("done"), 600);
  }

  if (status === "done") {
    return (
      <div className="flex flex-col items-center rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-14 text-center">
        <CheckCircle2 className="h-12 w-12 text-sps-gold" aria-hidden />
        <h3 className="mt-4 font-display text-xl font-semibold text-white">Thanks, {form.name.split(" ")[0] || "there"}!</h3>
        <p className="mt-2 max-w-sm text-sm text-white/60">
          Your message has been noted. (Heads up: email delivery isn&apos;t wired up yet, so this is a
          preview — we&apos;ll connect it before launch.)
        </p>
        <button
          type="button"
          onClick={() => { setForm({ name: "", email: "", subject: "", message: "" }); setStatus("idle"); }}
          className="mt-6 rounded-full bg-white/10 px-5 py-2.5 text-sm font-medium text-white ring-1 ring-white/15 hover:bg-white/15"
        >
          Send another
        </button>
      </div>
    );
  }

  const field = "mt-1.5 w-full rounded-lg border border-white/15 bg-white/[0.04] px-3.5 py-2.5 text-sm text-white placeholder:text-white/35 outline-none transition focus:border-sps-sky focus:bg-white/[0.06]";
  const label = "text-xs font-medium uppercase tracking-wide text-white/55";

  return (
    <form onSubmit={onSubmit} noValidate className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 sm:p-8">
      <p className="mb-5 rounded-lg bg-sps-gold/10 px-3 py-2 text-xs text-sps-gold/90">
        Note: this form is a preview — email delivery is not yet connected.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="c-name" className={label}>Name</label>
          <input id="c-name" className={field} value={form.name} onChange={update("name")} placeholder="Your name" autoComplete="name" />
        </div>
        <div>
          <label htmlFor="c-email" className={label}>Email</label>
          <input id="c-email" type="email" className={field} value={form.email} onChange={update("email")} placeholder="you@company.com" autoComplete="email" />
        </div>
      </div>
      <div className="mt-4">
        <label htmlFor="c-subject" className={label}>Subject</label>
        <input id="c-subject" className={field} value={form.subject} onChange={update("subject")} placeholder="How can we help?" />
      </div>
      <div className="mt-4">
        <label htmlFor="c-message" className={label}>Message</label>
        <textarea id="c-message" rows={5} className={field} value={form.message} onChange={update("message")} placeholder="Tell us a little about what you need…" />
      </div>
      {error && <p role="alert" className="mt-3 rounded-lg bg-[#3a1414] px-3 py-2 text-sm text-[#FCA5A5]">{error}</p>}
      <button
        type="submit"
        disabled={status === "submitting"}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-full bg-sps-blue px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sps-blue/25 transition hover:bg-sps-blue/90 disabled:opacity-60 sm:w-auto"
      >
        {status === "submitting" ? "Sending…" : <>Send message <Send size={15} /></>}
      </button>
    </form>
  );
}
