"use client";
/** Global marketing-site widgets (rendered ONLY from the (marketing) layout, so they
 *  never appear on the app portals, registration, or login):
 *   1. Scroll-to-top — floating button (accent-matched to the chat widget).
 *   2. Chat assistant — a RULE-BASED, menu-driven bot. Zero cost, front-end only:
 *      no backend, no API, no LLM. All answers are pre-written and accurate to our
 *      three verticals; quick-reply chips + branching + simple keyword matching for
 *      free text. Structured (TOPICS map) so it's easy to extend later.
 *  Both respect prefers-reduced-motion and are keyboard/aria accessible. */
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUp, MessageSquare, X, Send } from "lucide-react";

const ACCENT = "#1B5FE8";        // shared accent for BOTH floating widgets
const EMAIL = "info@spstechnosoft.com";
const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

type LinkItem = { label: string; href: string };
type Topic = { chip: string; answer: string; links?: LinkItem[]; next?: string[] };

// Pre-written, accurate to our 3 verticals — no invented services or prices.
const TOPICS: Record<string, Topic> = {
  services: {
    chip: "Our Services",
    answer: "We work across three connected verticals on one talent platform — staffing & recruitment, education & training, and IT services & consulting. Which one would you like to explore?",
    links: [{ label: "All services →", href: "/services" }],
    next: ["staffing", "edtech", "it"],
  },
  staffing: {
    chip: "Staffing & Recruitment",
    answer: "End-to-end hiring across permanent, contract, and remote roles — experienced recruiters plus AI-assisted matching, a large pre-screened candidate database, and a structured, quality-first process. You can sign in or post a job from this page too.",
    links: [{ label: "Staffing & Recruitment →", href: "/services/staffing" }],
  },
  edtech: {
    chip: "EdTech / Academy",
    answer: "Education, Training & Internships — live-project internships, corporate upskilling and L&D, and certification tracks that turn learners into job-ready talent.",
    links: [{ label: "EdTech / Academy →", href: "/services/education" }],
  },
  it: {
    chip: "IT Services & Consulting",
    answer: "Custom software, cloud & DevOps, AI/ML, data engineering, and digital transformation — delivered by our consulting team.",
    links: [{ label: "IT Services & Consulting →", href: "/services/it" }],
  },
  careers: {
    chip: "Careers",
    answer: "We hire for remote, contract, and permanent roles, and run an internship programme on live projects. See current openings and how to apply.",
    links: [{ label: "Careers →", href: "/career" }],
  },
  contact: {
    chip: "Contact Us",
    answer: `You can reach our team through the contact page, or email us directly at ${EMAIL}. We usually reply within a few hours.`,
    links: [{ label: "Contact us →", href: "/contact" }],
  },
  start: {
    chip: "How to get started",
    answer: "Easy! To hire, head to the Staffing & Recruitment page to post a job or sign in to your portal. Prefer to talk first? Send us a message via Contact.",
    links: [{ label: "Post a job / sign in →", href: "/services/staffing" }, { label: "Contact us →", href: "/contact" }],
  },
};

const ROOT = ["services", "staffing", "edtech", "it", "careers", "contact", "start"];
const GREETING = "Hi! 👋 I'm the SPSTechnosoft assistant. What would you like to know?";

// Simple keyword → topic matching for free text (ordered; first hit wins). No AI.
const KEYWORDS: [string[], string][] = [
  [["job", "hire", "hiring", "recruit", "staff", "candidate", "vacanc", "placement"], "staffing"],
  [["course", "training", "train", "intern", "learn", "edtech", "academy", "upskill", "student", "certif"], "edtech"],
  [["software", "develop", "cloud", "devops", "ai", "ml", "data", "mobile app", "consult", "website"], "it"],
  [["career", "apply", "job seeker", "resume", "openings"], "careers"],
  [["contact", "email", "phone", "reach", "talk", "call", "support"], "contact"],
  [["service", "what do you", "offer", "vertical"], "services"],
  [["start", "begin", "get started", "post a job", "sign in", "login", "demo"], "start"],
];

function matchTopic(text: string): string | null {
  const t = text.toLowerCase();
  for (const [kws, id] of KEYWORDS) if (kws.some((k) => t.includes(k))) return id;
  return null;
}

type Msg = { role: "bot" | "user"; text: string; links?: LinkItem[] };

function ChatAssistant({ onClose }: { onClose: () => void }) {
  const reduce = useReducedMotion();
  const [messages, setMessages] = useState<Msg[]>([{ role: "bot", text: GREETING }]);
  const [chips, setChips] = useState<string[]>(ROOT);
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  function respond(id: string) {
    if (id === "menu") {
      setMessages((m) => [...m, { role: "bot", text: "Sure — what would you like to know?" }]);
      setChips(ROOT);
      return;
    }
    const t = TOPICS[id];
    if (!t) return;
    setMessages((m) => [...m, { role: "bot", text: t.answer, links: t.links }]);
    setChips([...(t.next ?? []), "menu"]);
  }

  function pick(id: string) {
    const label = id === "menu" ? "Back to menu" : TOPICS[id]?.chip ?? id;
    setMessages((m) => [...m, { role: "user", text: label }]);
    respond(id);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    setMessages((m) => [...m, { role: "user", text }]);
    const id = matchTopic(text);
    if (id) {
      respond(id);
    } else {
      setMessages((m) => [...m, {
        role: "bot",
        text: "I can help with our services, careers, or contacting our team — pick an option below, or reach us directly.",
        links: [{ label: "Contact us →", href: "/contact" }],
      }]);
      setChips(ROOT);
    }
  }

  return (
    <motion.div
      role="dialog"
      aria-label="SPSTechnosoft chat assistant"
      initial={reduce ? false : { opacity: 0, y: 20, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={reduce ? { opacity: 0 } : { opacity: 0, y: 20, scale: 0.96 }}
      transition={{ duration: 0.22, ease: EASE }}
      className="fixed bottom-24 right-6 z-50 flex max-h-[min(34rem,calc(100vh-7rem))] w-[min(23rem,calc(100vw-3rem))] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-black/10"
      style={{ fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* header */}
      <div className="flex items-start justify-between gap-3 px-5 py-4 text-white" style={{ background: "linear-gradient(135deg, #0A1628, #1B5FE8)" }}>
        <div>
          <p className="font-bold leading-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>SPSTechnosoft Assistant</p>
          <p className="mt-0.5 text-xs text-white/70">Quick answers &amp; links · not a live agent</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close chat" className="rounded-lg p-1 text-white/80 hover:bg-white/10 hover:text-white">
          <X size={18} />
        </button>
      </div>

      {/* messages */}
      <div ref={scrollRef} aria-live="polite" className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}>
            <div
              className={`max-w-[85%] px-3.5 py-2.5 text-sm leading-relaxed ${m.role === "user" ? "rounded-2xl rounded-tr-sm text-white" : "rounded-2xl rounded-tl-sm"}`}
              style={m.role === "user" ? { background: ACCENT } : { background: "#F0F4FA", color: "#0A1628" }}
            >
              {m.text}
            </div>
            {m.links && m.links.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {m.links.map((l) => (
                  <Link key={l.href + l.label} href={l.href}
                    className="inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
                    style={{ background: ACCENT }}>
                    {l.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* quick-reply chips */}
      <div className="flex flex-wrap gap-2 border-t border-[#EAEEF3] px-4 py-3">
        {chips.map((id) => {
          const isMenu = id === "menu";
          return (
            <button key={id} type="button" onClick={() => pick(id)}
              className="rounded-full border px-3 py-1.5 text-xs font-semibold transition hover:bg-[#F0F4FA]"
              style={isMenu ? { borderColor: "#DDE4F0", color: "#5A6B8A" } : { borderColor: `${ACCENT}55`, color: ACCENT }}>
              {isMenu ? "☰ Back to menu" : TOPICS[id].chip}
            </button>
          );
        })}
      </div>

      {/* free-text input */}
      <form onSubmit={submit} className="flex items-center gap-2 border-t border-[#EAEEF3] px-3 py-3">
        <input
          aria-label="Type a message"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Type a question…"
          className="min-w-0 flex-1 rounded-lg border border-[#DDE4F0] px-3 py-2 text-sm outline-none focus:border-[#1B5FE8]"
        />
        <button type="submit" aria-label="Send" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white transition hover:opacity-90" style={{ background: ACCENT }}>
          <Send size={16} />
        </button>
      </form>
    </motion.div>
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
      {/* Scroll-to-top — accent-matched to the chat widget; hidden while chat is open */}
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
            className="fixed bottom-24 right-6 z-40 flex h-11 w-11 items-center justify-center rounded-full text-white shadow-lg transition-transform hover:scale-105"
            style={{ background: ACCENT }}
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
        className="fixed bottom-6 right-6 z-50 flex h-11 w-11 items-center justify-center rounded-full text-white shadow-xl transition-transform hover:scale-105"
        style={{ background: "linear-gradient(135deg, #0A1628, #1B5FE8)" }}
      >
        {chatOpen ? <X size={20} /> : <MessageSquare size={20} />}
      </button>

      <AnimatePresence>
        {chatOpen && <ChatAssistant onClose={() => setChatOpen(false)} />}
      </AnimatePresence>
    </>
  );
}
