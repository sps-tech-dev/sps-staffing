export interface CandidateOverview {
  applications: number; interviews: number; offers: number; profileComplete: number;
  recent: { id: string; job: string; stage: string }[];
}

/** F3a: the session user's applications with live B.5 stages. */
export interface MyApplication {
  id: string; job_id: string; job: string; stage: string; applied_at: string | null;
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
  version: number;   // F2a: optimistic-lock token for POST /transition
  candidate: { id: string; full_name: string; email: string | null;
               skills?: string[] | null; total_exp?: number | null };
}

export interface TimelineEvent {
  event_type: string; occurred_at: string; payload?: Record<string, unknown>;
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
export interface FeatureFlags { ai: boolean; assessment_waiver?: boolean; }
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
export interface ClientOverview {
  open_jobs: number; in_pipeline: number; interviews: number; offers: number;
  funnel: { label: string; value: number }[];
}
export interface ClientSubmission {
  id: string; status: string; client_feedback: string | null;
  candidate: string | null; job: string | null; stage: string | null; created_at: string | null;
}
export interface ClientPipeline { stages: Record<string, { id: string; candidate: string; job: string; stage: string }[]>; }
export interface ClientInterviewRow { id: string; scheduled_at: string | null; mode: string; status: string; candidate: string | null; }
export interface ClientOfferRow { id: string; status: string; ctc: number | null; joining_date: string | null; candidate: string | null; }
export type ClientRole = "client_admin" | "client_manager" | null;
export interface ClientMe {
  user_id: string; role: string; client_id: string | null; client_role: ClientRole; business_unit: string | null;
}
export interface ClientTeamMember { user_id: string; email: string; name: string | null; role: "client_admin" | "client_manager"; is_self: boolean; }

/** B.11 founder overview (aggregates only — the backend guard guarantees no PII). */
export interface FounderOverview {
  revenue_mtd: number; fees_billed_total: number; open_jobs: number;
  candidates_total: number; placements_total: number; placements_in_guarantee: number;
  pipeline_active: number; pipeline_funnel: Record<string, number>;
  assessment_pass_rate: number | null; notifications: Record<string, number>;
}

/** B.7 assessments (F5). A waived test has waived=true and score=null — the UI
 *  must NEVER render a numeric score for a waiver (the honesty guarantee). */
export interface TestRow {
  id: string; application_id: string; status: string; attempt_no: number;
  score: number | null; passed: boolean | null; waived: boolean;
  submitted_at: string | null; snapshots: number;
}
export interface IssueResult {
  test_id: string; take_path: string; valid_until: string; attempt_no: number;
  question_count: number; time_limit_minutes: number;
}
export interface TakeQuestion { qid: string; stem: string; options: string[] }
export interface TakePaper {
  questions: TakeQuestion[]; attempt_no: number; time_limit_minutes: number; expires_at: string;
}
export interface TakeResult {
  score: number; passed: boolean; already_submitted?: boolean; pipeline_advanced?: boolean;
}

/** B.12 CRM lead (F6). Stage vocabulary = the mini guard; won/lost terminal. */
export interface Lead {
  id: string; company: string; contact_name: string | null; contact_email: string | null;
  contact_phone: string | null; source: string | null; owner_id: string | null;
  stage: string; lost_reason: string | null; converted_client_id: string | null;
  business_unit_id: string; created_at: string | null;
}
export interface LeadActivity {
  id: string; type: string; notes: string | null; actor_id: string | null; occurred_at: string;
}
export interface ConvertResult extends Lead {
  client_id: string; job_id?: string; already_converted: boolean;
}

/** B.13 vendor depth (F6). */
export interface VendorContract {
  id: string; base_commission_percent: number; valid_from: string;
  valid_until: string | null; status: string;
}
export interface VendorClientRate { client_id: string; commission_percent: number }
export interface VendorCommission {
  id: string; placement_id: string; resolved_percent: number; base_amount: number;
  commission_amount: number; status: "accrued" | "paid" | "void"; void_reason: string | null;
}
export interface VendorScorecard {
  vendor_id: string; submissions: number; placements: number;
  conversion_rate: number | null; avg_time_to_fill_days: number | null;
  active_in_guarantee: number; commission_accrued: number; commission_paid: number;
}
export interface StaffClient { id: string; name: string; status: string }
