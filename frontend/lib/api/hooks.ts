"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AdminCandidate, AdminClient, AdminJobRow, AuditRow, CandidateOverview, EmployeeOverview,
  EmployerOverview, Job, JobPipeline, Paginated, PipelineRow,
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
