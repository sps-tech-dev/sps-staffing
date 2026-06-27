"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { CandidateOverview, EmployerOverview } from "./types";

/** Demo-safe: try the real read-model endpoint, fall back to mock so the starter
 *  runs with no backend. Delete the `.catch(() => MOCK)` when the API is live. */
export function useCandidateOverview() {
  return useQuery({
    queryKey: ["candidate", "overview"],
    queryFn: () => api<CandidateOverview>("/me/overview").catch(() => MOCK_CANDIDATE),
  });
}
export function useEmployerOverview() {
  return useQuery({
    queryKey: ["employer", "overview"],
    queryFn: () => api<EmployerOverview>("/client-portal/overview").catch(() => MOCK_EMPLOYER),
  });
}

const MOCK_CANDIDATE: CandidateOverview = {
  applications: 7, interviews: 2, offers: 1, profileComplete: 80,
  recent: [
    { id: "1", job: "PySpark Data Engineer", status: "interview", updatedAt: "2026-06-22" },
    { id: "2", job: "Senior Python Developer", status: "screening", updatedAt: "2026-06-20" },
    { id: "3", job: "AWS Solutions Architect", status: "applied", updatedAt: "2026-06-18" },
    { id: "4", job: "Backend Engineer", status: "rejected", updatedAt: "2026-06-15" },
  ],
};
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
