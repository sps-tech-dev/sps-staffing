"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { CandidateOverview, EmployerOverview, Job, JobPipeline } from "./types";

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
