export interface CandidateOverview {
  applications: number; interviews: number; offers: number; profileComplete: number;
  recent: { id: string; job: string; status: string; updatedAt: string }[];
}
export interface EmployerOverview {
  openJobs: number; inPipeline: number; interviews: number; placements: number;
  funnel: { label: string; value: number }[];
  pipeline: { id: string; candidate: string; job: string; stage: string }[];
}

export interface Job {
  id: string; title: string; client_id: string | null; status: string;
  skills: string[] | null; min_exp: number | null; max_exp: number | null;
}
export interface PipelineRow {
  id: string; job_id: string; candidate_id: string; stage: string;
  candidate: { id: string; full_name: string; email: string | null };
}
export interface JobPipeline {
  job: Job;
  stages: Record<string, PipelineRow[]>;
}

export interface QueueItem {
  id: string; candidate: string; job: string; stage: string;
  ageHours: number; sla: "ok" | "warning" | "breached"; slaTargetHours: number;
}
export interface EmployeeOverview {
  open: number; breaching: number; breached: number; queue: QueueItem[];
}

export interface Paginated<T> { items: T[]; total: number; limit: number; offset: number; }
export interface AdminCandidate {
  id: string; full_name: string; email: string | null; phone: string | null;
  skills: string[] | null; total_exp: number | null; created_at: string | null;
}
export interface AdminClient { id: string; name: string; industry: string | null; status: string; }
export interface AdminJobRow { id: string; title: string; status: string; }
export interface AuditRow {
  id: number; action: string; entity: string; entity_id: string | null;
  actor_id: string | null; ts: string | null;
}
