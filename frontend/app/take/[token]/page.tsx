"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle2, XCircle, Clock, ShieldAlert, Camera } from "lucide-react";
import type { TakePaper, TakeResult } from "@/lib/api/types";

/** F5: the PUBLIC aptitude take page. Token-gated (no JWT, no portal shell —
 *  this route lives OUTSIDE the (portal)/(admin) groups on purpose). The paper
 *  the server sends contains stems + shuffled options ONLY — correct answers
 *  never leave the server (B.7); this page never expects a `correct` field.
 *
 *  Proctoring status: PRESIGN-ONLY. The page requests one snapshot-upload URL to
 *  prove the wiring; the actual capture loop (webcam/face-api/fullscreen
 *  lockdown) is deferred per B.7's PENDING and is NOT built here. */

type PageState =
  | { kind: "loading" }
  | { kind: "invalid" }                       // 404 — generic, no enumeration hint
  | { kind: "gone" }                          // 410 — expired / used / waived
  | { kind: "paper"; paper: TakePaper }
  | { kind: "result"; result: TakeResult };

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-dvh items-start justify-center bg-page px-4 py-10">
      <div className="w-full max-w-2xl">
        <header className="mb-6 text-center">
          <p className="font-display text-lg font-bold text-ink">SPS Technosoft — Aptitude Test</p>
        </header>
        {children}
      </div>
    </main>
  );
}

function Notice({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-cardline bg-card p-8 text-center shadow-sm">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-page text-muted">{icon}</div>
      <h1 className="mt-3 font-display text-lg font-bold text-ink">{title}</h1>
      <p className="mt-2 text-sm text-muted">{body}</p>
    </div>
  );
}

export default function TakePage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [proctorReady, setProctorReady] = useState(false);
  const submittedRef = useRef(false);

  const submit = useCallback(async (auto = false) => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/take/${token}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ answers }),
      });
      if (res.status === 410) { setState({ kind: "gone" }); return; }
      if (!res.ok) { submittedRef.current = false; setSubmitting(false); return; }
      setState({ kind: "result", result: await res.json() });
    } catch {
      submittedRef.current = false;
      setSubmitting(false);
      if (!auto) alert("Network error — your answers were not submitted. Please retry.");
    }
  }, [token, answers]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const res = await fetch(`/api/take/${token}`);
      if (!alive) return;
      if (res.status === 404) { setState({ kind: "invalid" }); return; }
      if (res.status === 410) { setState({ kind: "gone" }); return; }
      if (!res.ok) { setState({ kind: "invalid" }); return; }
      const paper: TakePaper = await res.json();
      setState({ kind: "paper", paper });
      setSecondsLeft(paper.time_limit_minutes * 60);
      // presign-only proctoring wiring (see module docstring)
      fetch(`/api/take/${token}/snapshot/presign`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content_type: "image/jpeg" }),
      }).then((r) => setProctorReady(r.ok)).catch(() => setProctorReady(false));
    })();
    return () => { alive = false; };
  }, [token]);

  useEffect(() => {
    if (secondsLeft == null || state.kind !== "paper") return;
    if (secondsLeft <= 0) { void submit(true); return; }   // timer auto-submit at 0
    const t = setTimeout(() => setSecondsLeft((s) => (s == null ? s : s - 1)), 1000);
    return () => clearTimeout(t);
  }, [secondsLeft, state.kind, submit]);

  if (state.kind === "loading") {
    return <Shell><div className="h-40 animate-pulse rounded-2xl bg-card" /></Shell>;
  }
  if (state.kind === "invalid") {
    return <Shell><Notice icon={<ShieldAlert size={24} />} title="Invalid link"
      body="This test link isn't valid. Please contact your recruiter." /></Shell>;
  }
  if (state.kind === "gone") {
    return <Shell><Notice icon={<Clock size={24} />} title="This link is no longer valid"
      body="The test link has expired or was already used. Contact your recruiter if you believe this is an error." /></Shell>;
  }
  if (state.kind === "result") {
    const r = state.result;
    return (
      <Shell>
        <div className="rounded-2xl border border-cardline bg-card p-8 text-center shadow-sm">
          <div className={`mx-auto flex h-12 w-12 items-center justify-center rounded-2xl ${r.passed ? "bg-[#F0FDF4] text-[#16A34A]" : "bg-[#FEF2F2] text-[#DC2626]"}`}>
            {r.passed ? <CheckCircle2 size={24} /> : <XCircle size={24} />}
          </div>
          <h1 className="mt-3 font-display text-lg font-bold text-ink">
            {r.passed ? "Congratulations — you passed!" : "Test complete"}
          </h1>
          <p className="mt-2 text-sm text-muted">
            Your score: <strong className="text-ink">{(r.score * 100).toFixed(0)}%</strong>
            {r.already_submitted && " (previously submitted — this is your stored result)"}
          </p>
          <p className="mt-1 text-xs text-muted">
            {r.passed ? "Our team will contact you about next steps." : "Thank you for taking the test. Your recruiter will be in touch."}
          </p>
        </div>
      </Shell>
    );
  }

  const { paper } = state;
  const answered = Object.keys(answers).length;
  const mm = secondsLeft != null ? Math.floor(secondsLeft / 60) : 0;
  const ss = secondsLeft != null ? secondsLeft % 60 : 0;
  return (
    <Shell>
      <div className="sticky top-0 z-10 mb-4 flex items-center justify-between rounded-xl border border-cardline bg-card px-4 py-2.5 shadow-sm">
        <span className="text-xs text-muted">
          {answered}/{paper.questions.length} answered · attempt #{paper.attempt_no}
          {proctorReady && (
            <span className="ml-2 inline-flex items-center gap-1 text-[10px] text-muted">
              <Camera size={10} /> proctoring session ready
            </span>
          )}
        </span>
        <span className={`inline-flex items-center gap-1 font-mono text-sm font-semibold ${secondsLeft != null && secondsLeft < 300 ? "text-[#DC2626]" : "text-ink"}`}>
          <Clock size={14} /> {mm}:{String(ss).padStart(2, "0")}
        </span>
      </div>

      <div className="space-y-4">
        {paper.questions.map((q, qi) => (
          <fieldset key={q.qid} className="rounded-2xl border border-cardline bg-card p-5 shadow-sm">
            <legend className="sr-only">Question {qi + 1}</legend>
            <p className="text-sm font-medium text-ink">{qi + 1}. {q.stem}</p>
            <div className="mt-3 space-y-1.5">
              {q.options.map((opt, oi) => (
                <label key={oi} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${answers[q.qid] === oi ? "border-[#1B5FE8] bg-[#EFF6FF] text-ink" : "border-cardline text-ink hover:bg-page"}`}>
                  <input type="radio" name={q.qid} checked={answers[q.qid] === oi}
                    onChange={() => setAnswers((a) => ({ ...a, [q.qid]: oi }))} className="accent-[#1B5FE8]" />
                  {opt}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
      </div>

      <div className="mt-6 flex items-center justify-between rounded-xl border border-cardline bg-card px-4 py-3 shadow-sm">
        <p className="text-xs text-muted">Unanswered questions are marked wrong. Submitting is final.</p>
        <button onClick={() => void submit()} disabled={submitting}
          className="rounded-lg bg-sps-blue px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {submitting ? "Submitting…" : "Submit test"}
        </button>
      </div>
    </Shell>
  );
}
