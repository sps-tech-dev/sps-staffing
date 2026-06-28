"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AdminCandidate, AdminClient, AdminJobRow, AiSummary, AuditRow, CandidateOverview,
  ConsentState, DpdpRequestRow, EmployeeOverview, EmployerOverview, FeatureFlags,
  Job, JobPipeline, Offer, Paginated, PipelineRow, RegistrationConfig, RegistrationResult,
  Submission,
} from "./types";

const PAGE = 20;
const qs = (offset: number, limit: number, q?: string) =>
  `?limit=${limit}&offset=${offset}` + (q ? `&q=${encodeURIComponent(q)}` : "");

/** Candidate overview — REAL read-model (Slice 2). Authenticated + tenant-scoped;
 *  errors surface so the page shows an error state (no silent mock fallback). */
export function useCandidateOverview() {
  return useQuery({
    queryKey: ["candidate", "overview"],
    queryFn: () => api<CandidateOverview>("/me/overview"),
    retry: false,
  });
}

/** Employer overview — REAL read-model (Slice 3). */
export function useEmployerOverview() {
  return useQuery({
    queryKey: ["employer", "overview"],
    queryFn: () => api<EmployerOverview>("/client-portal/overview"),
    retry: false,
  });
}

/** Admin console lists (Slice 6) — paginated, admin-gated. */
export function useAdminCandidates(offset = 0, q = "") {
  return useQuery({
    queryKey: ["admin", "candidates", offset, q],
    queryFn: () => api<Paginated<AdminCandidate>>(`/admin/candidates${qs(offset, PAGE, q)}`),
    retry: false,
  });
}
export function useAdminClients(offset = 0) {
  return useQuery({
    queryKey: ["admin", "clients", offset],
    queryFn: () => api<Paginated<AdminClient>>(`/admin/clients${qs(offset, PAGE)}`),
    retry: false,
  });
}
export function useAdminJobs(offset = 0) {
  return useQuery({
    queryKey: ["admin", "jobs", offset],
    queryFn: () => api<Paginated<AdminJobRow>>(`/admin/jobs${qs(offset, PAGE)}`),
    retry: false,
  });
}
export function useAdminAuditLogs(offset = 0) {
  return useQuery({
    queryKey: ["admin", "audit", offset],
    queryFn: () => api<Paginated<AuditRow>>(`/admin/audit-logs${qs(offset, 50)}`),
    retry: false,
  });
}

// ── F6: feature flags + DPDP self-service ───────────────────────
/** Feature flags for this user — gates client widgets (e.g. AI). */
export function useFeatures() {
  return useQuery({
    queryKey: ["me", "features"],
    queryFn: () => api<{ features: FeatureFlags }>("/me/features"),
    retry: false,
  });
}

/** AI candidate summary — gated server-side (404 when flag off). `enabled`
 *  should be the resolved feature flag so we don't fire a request that 404s. */
export function useAiCandidateSummary(candidateId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["ai", "candidate-summary", candidateId],
    queryFn: () => api<AiSummary>(`/ai/candidate-summary/${candidateId}`),
    enabled: enabled && !!candidateId,
    retry: false,
  });
}

/** Current DPDP consent state for the logged-in user. */
export function useConsent() {
  return useQuery({
    queryKey: ["privacy", "consent"],
    queryFn: () => api<ConsentState>("/privacy/consent"),
    retry: false,
  });
}

/** Record a consent grant/withdraw; refreshes consent state. */
export function useSetConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { purpose: string; granted: boolean }) =>
      api("/privacy/consent", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["privacy", "consent"] }),
  });
}

/** Export the principal's data (returns the bundle inline); refreshes history. */
export function useExportData() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ request_id: string; data: unknown }>("/privacy/export", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["privacy", "requests"] }),
  });
}

/** Request erasure (records a pending request); refreshes history. */
export function useRequestErasure() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<DpdpRequestRow>("/privacy/erase", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["privacy", "requests"] }),
  });
}

/** The principal's DPDP request history (export/erasure). */
export function useDpdpRequests() {
  return useQuery({
    queryKey: ["privacy", "requests"],
    queryFn: () => api<{ items: DpdpRequestRow[] }>("/privacy/requests"),
    retry: false,
  });
}

// ── Public candidate registration ───────────────────────────────
/** Registration page config — captcha sitekey + (stubbed) consent notices. */
export function useRegistrationConfig() {
  return useQuery({
    queryKey: ["register", "config"],
    queryFn: () => api<RegistrationConfig>("/register/config"),
    retry: false,
  });
}

/** Submit a candidate registration (public; PII encrypted server-side). */
export function useRegisterCandidate() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<RegistrationResult>("/register/candidate", { method: "POST", body: JSON.stringify(body) }),
  });
}

// ── Staffing workflow: submissions ──────────────────────────────
export function useSubmissions() {
  return useQuery({ queryKey: ["submissions"], queryFn: () => api<Submission[]>("/submissions"), retry: false });
}
export function useCreateSubmission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (appId: string) => api<Submission>(`/applications/${appId}/submissions`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["submissions"] }),
  });
}
export function useUpdateSubmission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; status?: string; client_feedback?: string }) =>
      api<Submission>(`/submissions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["submissions"] }),
  });
}

// ── Staffing workflow: offers ───────────────────────────────────
export function useOffers() {
  return useQuery({ queryKey: ["offers"], queryFn: () => api<Offer[]>("/offers"), retry: false });
}
export function useCreateOffer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (appId: string) => api<Offer>(`/applications/${appId}/offers`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["offers"] }),
  });
}
export function useUpdateOffer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; status?: string; ctc?: number; joining_date?: string; rtr_signed?: boolean }) =>
      api<Offer>(`/offers/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["offers"] }),
  });
}

/** Employee/recruiter SLA hub overview (Slice 5). */
export function useEmployeeOverview() {
  return useQuery({
    queryKey: ["employee", "overview"],
    queryFn: () => api<EmployeeOverview>("/employee/overview"),
    retry: false,
  });
}

/** Jobs list (Slice 3). */
export function useJobs() {
  return useQuery({ queryKey: ["jobs"], queryFn: () => api<Job[]>("/jobs"), retry: false });
}

/** Create a job; refreshes the jobs list + employer overview. */
export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string }) =>
      api<Job>("/jobs", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["employer", "overview"] });
    },
  });
}

/** A job's pipeline (applications grouped by stage). */
export function useJobPipeline(jobId: string | null) {
  return useQuery({
    queryKey: ["pipeline", jobId],
    queryFn: () => api<JobPipeline>(`/jobs/${jobId}/pipeline`),
    enabled: !!jobId,
    retry: false,
  });
}

function moveCard(data: JobPipeline | undefined, appId: string, toStage: string): JobPipeline | undefined {
  if (!data) return data;
  const stages: Record<string, PipelineRow[]> = { ...data.stages };
  let moved: PipelineRow | undefined;
  for (const s of Object.keys(stages)) {
    const idx = stages[s].findIndex((r) => r.id === appId);
    if (idx >= 0) {
      moved = { ...stages[s][idx], stage: toStage };
      stages[s] = [...stages[s].slice(0, idx), ...stages[s].slice(idx + 1)];
      break;
    }
  }
  if (moved) stages[toStage] = [moved, ...(stages[toStage] ?? [])];
  return { ...data, stages };
}

/** Optimistic stage move (Slice 4) — updates the board immediately, reverts on
 *  error (e.g. a 409 illegal transition from the server), reconciles on settle. */
export function useChangeStage(jobId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ appId, stage }: { appId: string; stage: string }) =>
      api(`/applications/${appId}/stage`, { method: "PATCH", body: JSON.stringify({ stage }) }),
    onMutate: async ({ appId, stage }) => {
      await qc.cancelQueries({ queryKey: ["pipeline", jobId] });
      const prev = qc.getQueryData<JobPipeline>(["pipeline", jobId]);
      qc.setQueryData<JobPipeline | undefined>(["pipeline", jobId], (old) => moveCard(old, appId, stage));
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(["pipeline", jobId], ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["pipeline", jobId] });
      qc.invalidateQueries({ queryKey: ["employer", "overview"] });
    },
  });
}
