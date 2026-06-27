/** Mirrors the backend feature-flag service. Off features hide UI and 404 routes. */
export type FlagKey = "recruiterCopilot" | "candidateAssistant" | "semanticMatch" | "slaPrecisionTimers";

export const FLAGS: Record<FlagKey, boolean> = {
  recruiterCopilot: false,
  candidateAssistant: false,
  semanticMatch: false,     // pgvector
  slaPrecisionTimers: false,
};

export const isEnabled = (k: FlagKey) => FLAGS[k];
