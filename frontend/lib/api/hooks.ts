"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AdminCandidate, AdminClient, AdminJobRow, AiSummary, AuditRow, CandidateOverview,
  ConsentState, DpdpRequestRow, EmployeeOverview, EmployerOverview, FeatureFlags,
  ClientInterviewRow, ClientOfferRow, ClientOverview, ClientPipeline, ClientRegistration,
  ClientSubmission, Interview, Invoice, Job, JobPipeline, Offer, Paginated, PipelineRow,
  RegistrationConfig, RegistrationResult, Submission, Vendor, VendorSubmission,
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

// ── Client self-service portal (scoped to the session's client_id) ──
export function useClientOverview() {
  return useQuery({ queryKey: ["client", "overview"], queryFn: () => api<ClientOverview>("/client/overview"), retry: false });
}
export function useClientJobs() {
  return useQuery({ queryKey: ["client", "jobs"], queryFn: () => api<Job[]>("/client/jobs"), retry: false });
}
export function useClientPipeline() {
  return useQuery({ queryKey: ["client", "pipeline"], queryFn: () => api<ClientPipeline>("/client/pipeline"), retry: false });
}
export function useClientSubmissions() {
  return useQuery({ queryKey: ["client", "submissions"], queryFn: () => api<ClientSubmission[]>("/client/submissions"), retry: false });
}
export function useClientInterviews() {
  return useQuery({ queryKey: ["client", "interviews"], queryFn: () => api<ClientInterviewRow[]>("/client/interviews"), retry: false });
}
export function useClientOffers() {
  return useQuery({ queryKey: ["client", "offers"], queryFn: () => api<ClientOfferRow[]>("/client/offers"), retry: false });
}
export function useClientSubmissionFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision, note }: { id: string; decision: "approve" | "reject"; note?: string }) =>
      api(`/client/submissions/${id}/feedback`, { method: "POST", body: JSON.stringify({ decision, note }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["client", "submissions"] }),
  });
}
export function useClientPostJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; jd_text?: string; skills?: string[] }) =>
      api<Job>("/client/jobs", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["client", "jobs"] }); qc.invalidateQueries({ queryKey: ["client", "overview"] }); },
  });
}

// ── Admin: client-registration approval gate ────────────────────
export function useClientRegistrations(status = "pending") {
  return useQuery({
    queryKey: ["admin", "client-registrations", status],
    queryFn: () => api<Paginated<ClientRegistration>>(`/admin/client-registrations?status=${status}`),
    retry: false,
  });
}
export function useApproveClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; create_new_client?: boolean; client_id?: string; initial_password: string }) =>
      api(`/admin/client-registrations/${id}/approve`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "client-registrations"] }),
  });
}
export function useRejectClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/admin/client-registrations/${id}/reject`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "client-registrations"] }),
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

/** Submit a CLIENT (company) registration → a pending request (no access until approved). */
export function useRegisterClient() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<RegistrationResult>("/register/client", { method: "POST", body: JSON.stringify(body) }),
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

// ── Staffing workflow: interviews ───────────────────────────────
export function useInterviews() {
  return useQuery({ queryKey: ["interviews"], queryFn: () => api<Interview[]>("/interviews"), retry: false });
}
export function useCreateInterview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (appId: string) => api<Interview>(`/applications/${appId}/interviews`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["interviews"] }),
  });
}
export function useUpdateInterview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; scheduled_at?: string; mode?: string; status?: string; interviewer_name?: string; feedback?: string }) =>
      api<Interview>(`/interviews/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["interviews"] }),
  });
}

// ── Staffing workflow: invoices ─────────────────────────────────
export function useInvoices() {
  return useQuery({ queryKey: ["invoices"], queryFn: () => api<Invoice[]>("/invoices"), retry: false });
}
export function useCreateInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { application_id: string; base_amount: number; fee_percent?: number }) =>
      api<Invoice>("/invoices", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoices"] }),
  });
}
export function useUpdateInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; status?: string; gst_percent?: number; tds_percent?: number }) =>
      api<Invoice>(`/invoices/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoices"] }),
  });
}

// ── Staffing workflow: vendors ──────────────────────────────────
export function useVendors() {
  return useQuery({ queryKey: ["vendors"], queryFn: () => api<Vendor[]>("/vendors"), retry: false });
}
export function useCreateVendor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; contact_email?: string; commission_percent?: number }) =>
      api<Vendor>("/vendors", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vendors"] }),
  });
}
export function useUpdateVendor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; status?: string; commission_percent?: number }) =>
      api<Vendor>(`/vendors/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vendors"] }),
  });
}
export function useVendorSubmissions() {
  return useQuery({ queryKey: ["vendor-submissions"], queryFn: () => api<VendorSubmission[]>("/vendor-submissions"), retry: false });
}
export function useUpdateVendorSubmission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; status?: string; notes?: string }) =>
      api<VendorSubmission>(`/vendor-submissions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vendor-submissions"] }),
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
