"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { CandidateOverview, EmployerOverview } from "./types";

/** Candidate overview — REAL read-model (Slice 2). Authenticated + tenant-scoped;
 *  errors surface so the page shows an error state (no silent mock fallback). */
export function useCandidateOverview() {
  return useQuery({
    queryKey: ["candidate", "overview"],
    queryFn: () => api<CandidateOverview>("/me/overview"),
    retry: false,
  });
}

/** Employer overview — still mock until its read-model lands (Slice 4). */
export function useEmployerOverview() {
  return useQuery({
    queryKey: ["employer", "overview"],
    queryFn: () => api<EmployerOverview>("/client-portal/overview").catch(() => MOCK_EMPLOYER),
  });
}

const MOCK_EMPLOYER: EmployerOverview = {
  openJobs: 12, inPipeline: 48, interviews: 9, placements: 5,
  funnel: [
    { label: "Screening", value: 22 }, { label: "TR1", value: 12 },
    { label: "TR2", value: 8 }, { label: "HR", value: 4 }, { label: "Offer", value: 2 },
  ],
  pipeline: [
    { id: "1", candidate: "A. Sharma", job: "PySpark Dev", stage: "interview" },
    { id: "2", candidate: "R. Mehta", job: "Python Dev", stage: "screening" },
    { id: "3", candidate: "K. Iyer", job: "AWS Architect", stage: "selected" },
  ],
};
