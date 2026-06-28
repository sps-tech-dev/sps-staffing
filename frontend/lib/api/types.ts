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

// F6 — feature flags + DPDP self-service
export interface FeatureFlags { ai: boolean; }
export interface ConsentState {
  policy_version: string;
  notices: Record<string, string>;
  purposes: Record<string, boolean>;
}
export interface DpdpRequestRow { id: string; kind: string; status: string; created_at: string | null; }
export interface AiSummary {
  candidate_id: string; stub: boolean; summary: string; highlights: string[]; disclaimer: string;
}

// Candidate self-registration
export interface RegistrationConfig {
  hcaptcha_sitekey: string;
  policy_version: string;
  notices: { data_processing: string; marketing: string };
}
export interface RegistrationResult { id: string; status: string; policy_version: string; }

// Staffing workflow
export interface Submission {
  id: string; application_id: string; status: string; client_feedback: string | null;
  created_at: string | null; candidate?: string; job?: string;
}
export interface Offer {
  id: string; application_id: string; ctc: number | null; joining_date: string | null;
  status: string; rtr_signed_at: string | null; accepted_at: string | null;
  created_at: string | null; candidate?: string; job?: string;
}
export interface Interview {
  id: string; application_id: string; scheduled_at: string | null; mode: string; status: string;
  interviewer_name: string | null; feedback: string | null; created_at: string | null;
  candidate?: string; job?: string;
}
export interface Invoice {
  id: string; application_id: string; client_id: string | null;
  base_amount: number | null; fee_percent: number | null; fee_amount: number | null;
  gst_percent: number | null; gst_amount: number | null; tds_percent: number | null; tds_amount: number | null;
  total_amount: number | null; currency: string; status: string; created_at: string | null;
  candidate?: string; job?: string;
}
export interface Vendor {
  id: string; name: string; contact_email: string | null; contact_phone: string | null;
  commission_percent: number | null; status: string;
}
export interface VendorSubmission {
  id: string; vendor_id: string; candidate_id: string; job_id: string | null; status: string;
  notes: string | null; created_at: string | null; vendor?: string; candidate?: string;
}

// Client portal
export interface ClientRegistration {
  id: string; company_name: string; industry: string | null; contact_person: string;
  email: string; phone: string | null; website: string | null; company_size: string | null;
  status: string; created_at: string | null;
}
