"use client";
/* eslint-disable react/no-unescaped-entities */
/** Global marketing-site widgets (rendered ONLY from the (marketing) layout, so they
 *  never appear on the app portals, registration, or login):
 *   1. Scroll-to-top — floating button, appears past a scroll threshold, smooth-scrolls
 *      to top (pattern adapted from the reference's footer "Back to top" +
 *      navbar `scrollY` threshold; re-skinned to our brand and made a floating FAB).
 *   2. Chat widget — a "Chat with us" contact panel. FRONT-END ONLY (no AI/LLM/paid
 *      backend): greeting + a short message form (composes a mailto) + email/WhatsApp
 *      quick links. Structured so a real backend can be dropped in later.
 *  Both respect prefers-reduced-motion and are keyboard/aria accessible. */
import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUp, MessageSquare, X, Mail, Phone, Send, CheckCircle2 } from "lucide-react";

const EMAIL = "hello@spstechnosoft.com";
const WHATSAPP = "https://wa.me/919876543210"; // placeholder — swap for the real number
const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

function ChatForm() {
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState(false);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!message.trim()) return;
    // No backend yet — compose an email the visitor can send from their client.
    const subject = encodeURIComponent(`Website enquiry${name ? ` from ${name}` : ""}`);
    const body = encodeURIComponent(message);
    window.location.href = `mailto:${EMAIL}?subject=${subject}&body=${body}`;
    setSent(true);
  }

  if (sent) {
    return (
      <div className="mt-3 flex flex-col items-center rounded-xl bg-[#F0F4FA] px-4 py-6 text-center">
        <CheckCircle2 size={28} style={{ color: "#1B5FE8" }} />
        <p className="mt-2 text-sm font-semibold" style={{ color: "#0A1628" }}>Thanks{name ? `, ${name.split(" ")[0]}` : ""}!</p>
        <p className="mt-1 text-xs" style={{ color: "#5A6B8A" }}>Your email app should have opened. We'll reply soon.</p>
      </div>
    );
  }

  const field = "w-full rounded-lg border border-[#DDE4F0] bg-white px-3 py-2 text-sm outline-none focus:border-[#1B5FE8]";
  return (
    <form onSubmit={onSubmit} className="mt-3 space-y-2">
      <input aria-label="Your name" className={field} placeholder="Your name (optional)" value={name} onChange={(e) => setName(e.target.value)} />
      <textarea aria-label="Your message" required rows={3} className={field} placeholder="How can we help?" value={message} onChange={(e) => setMessage(e.target.value)} />
      <button type="submit" className="inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition hover:opacity-90" style={{ background: "#1B5FE8" }}>
        Send message <Send size={15} />
      </button>
    </form>
  );
}

export function SiteWidgets() {
  const reduce = useReducedMotion();
  const [showTop, setShowTop] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setShowTop(window.scrollY > 400);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!chatOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setChatOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chatOpen]);

  const toTop = () => window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });

  return (
    <>
      {/* Scroll-to-top — hidden while the chat panel is open so they never overlap */}
      <AnimatePresence>
        {showTop && !chatOpen && (
          <motion.button
            type="button"
            onClick={toTop}
            aria-label="Scroll back to top"
            initial={reduce ? false : { opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-24 right-6 z-40 flex h-11 w-11 items-center justify-center rounded-full bg-white shadow-lg ring-1 ring-black/5 transition-colors hover:bg-[#F0F4FA]"
            style={{ color: "#0A1628" }}
          >
            <ArrowUp size={20} />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat FAB */}
      <button
        type="button"
        onClick={() => setChatOpen((v) => !v)}
        aria-label={chatOpen ? "Close chat" : "Chat with us"}
        aria-expanded={chatOpen}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full text-white shadow-xl transition-transform hover:scale-105"
        style={{ background: "linear-gradient(135deg, #0A1628, #1B5FE8)" }}
      >
        {chatOpen ? <X size={22} /> : <MessageSquare size={22} />}
      </button>

      {/* Chat panel */}
      <AnimatePresence>
        {chatOpen && (
          <motion.div
            role="dialog"
            aria-label="Chat with SPSTechnosoft"
            initial={reduce ? false : { opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: 20, scale: 0.96 }}
            transition={{ duration: 0.22, ease: EASE }}
            className="fixed bottom-24 right-6 z-50 w-[min(22rem,calc(100vw-3rem))] overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-black/10"
            style={{ fontFamily: "'DM Sans', sans-serif" }}
          >
            <div className="px-5 py-4 text-white" style={{ background: "linear-gradient(135deg, #0A1628, #1B5FE8)" }}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-bold leading-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>Chat with SPSTechnosoft</p>
                  <p className="mt-0.5 text-xs text-white/70">We usually reply within a few hours.</p>
                </div>
                <button type="button" onClick={() => setChatOpen(false)} aria-label="Close chat" className="rounded-lg p-1 text-white/80 hover:bg-white/10 hover:text-white">
                  <X size={18} />
                </button>
              </div>
            </div>

            <div className="px-5 py-4">
              <div className="rounded-2xl rounded-tl-sm bg-[#F0F4FA] px-4 py-3 text-sm" style={{ color: "#0A1628" }}>
                👋 Hi! Tell us what you need — hiring, training, or a project — and we'll get back to you.
              </div>

              <ChatForm />

              <div className="mt-4 grid grid-cols-2 gap-2">
                <a href={`mailto:${EMAIL}`} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[#DDE4F0] px-3 py-2 text-xs font-semibold transition hover:bg-[#F0F4FA]" style={{ color: "#0A1628" }}>
                  <Mail size={14} style={{ color: "#1B5FE8" }} /> Email us
                </a>
                <a href={WHATSAPP} target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[#DDE4F0] px-3 py-2 text-xs font-semibold transition hover:bg-[#F0F4FA]" style={{ color: "#0A1628" }}>
                  <Phone size={14} style={{ color: "#059669" }} /> WhatsApp
                </a>
              </div>

              <p className="mt-3 text-center text-[11px]" style={{ color: "#94A3B8" }}>
                Contact widget — a team member follows up personally.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
