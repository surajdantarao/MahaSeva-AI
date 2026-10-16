export type Language = 'en' | 'mr';

export interface SchemeItem {
  id: number;
  title: string;
  title_mr?: string;
  department: string;
  category: string;
  target_beneficiaries?: string;
  application_mode?: string;
  source_url: string;
  source_type: string;
  provider_classification: string;
  verification_status: 'pending_review' | 'verified' | 'rejected' | 'needs_update' | 'outdated';
  current_window_status: string;
  status_label_en?: string;
  status_label_mr?: string;
  badge_class?: string;
  application_start_date?: string | null;
  application_deadline?: string | null;
  closing_time?: string | null;
  no_deadline_notice_en?: string | null;
  no_deadline_notice_mr?: string | null;
  brief_description?: string;
  benefits?: string;
  eligibility?: string;
  official_apply_url?: string;
  pdf_urls?: string[];
  is_recently_announced?: boolean;
  is_recently_updated?: boolean;
  retrieved_at_utc?: string;
  last_checked_at?: string | null;
  notes?: string;
}

export interface ApplicationWindowItem {
  id: number;
  window_name: string;
  start_date?: string | null;
  deadline_date?: string | null;
  closing_time?: string | null;
  window_status: string;
  date_verification_status: string;
  official_source_url?: string;
  notes?: string;
}

export interface SchemeDetail extends SchemeItem {
  text: string;
  documents_required?: string;
  application_process?: string;
  last_reviewed_at?: string | null;
  reviewed_by?: string | null;
  imported_at: string;
  application_windows?: ApplicationWindowItem[];
}

export interface DepartmentInfo {
  name: string;
  total_schemes: number;
  verified_schemes: number;
}

export interface SchemeSummary {
  total_candidates: number;
  verified_count: number;
  pending_count: number;
  statuses: Record<string, number>;
  deadline_statuses?: Record<string, number>;
  department_counts: Record<string, number>;
  category_counts?: Record<string, number>;
}

export interface AISource {
  id: number;
  title: string;
  title_mr?: string;
  department: string;
  source_url: string;
  official_apply_url?: string;
  verification_status: string;
  current_window_status?: string;
  application_deadline?: string | null;
  provider_classification?: string;
}

export interface AIResponse {
  answer: string;
  sources: AISource[];
  confidence: string;
  language: string;
  disclaimer: string;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface AuditLogItem {
  id: number;
  candidate_id: number;
  reviewer_username: string;
  action: string;
  previous_status: string;
  new_status: string;
  notes: string;
  created_at: string;
}

export interface SchemeChangeItem {
  id: number;
  scheme_id?: number | null;
  change_type: string;
  field_name?: string | null;
  previous_value?: string | null;
  new_value?: string | null;
  evidence_text?: string | null;
  source_url: string;
  detection_timestamp: string;
  review_status: string;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_notes?: string | null;
}

export interface CollectionRunItem {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  total_candidates: number;
  new_candidates: number;
  updated_candidates: number;
  errors_count: number;
  log_summary: string;
}

export interface ConfiguredSourceItem {
  id: number;
  name: string;
  department?: string;
  source_category?: string;
  start_urls: string[];
  allowed_domains: string[];
  provider_hint: string;
  priority?: string;
  monitoring_frequency_hours?: number;
  last_crawled_at: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  url?: string;
  verification_status?: string;
}

export interface HomepageSectionGroup {
  title_en: string;
  title_mr: string;
  count: number;
  items: SchemeItem[];
}

export interface CategoryInfo {
  name: string;
  name_mr: string;
  icon: string;
  total_schemes: number;
  verified_schemes: number;
}

export interface ApplicationGuideResponse {
  scheme_id: number;
  title: string;
  title_mr: string;
  department: string;
  application_mode: string;
  official_apply_url?: string | null;
  official_source_url: string;
  documents_required: string;
  guide_en: string;
  guide_mr: string;
}

export interface EligibilityResponse {
  scheme_id: number;
  scheme_title: string;
  assessment_category: string;
  answer: string;
  matched_criteria?: string[];
  missing_criteria?: string[];
  official_source_url: string;
  official_apply_url?: string;
}
