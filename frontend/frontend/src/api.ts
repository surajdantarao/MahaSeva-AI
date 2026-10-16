import type {
  AdminUser,
  AIResponse,
  ApplicationGuideResponse,
  AuditLogItem,
  CategoryInfo,
  CollectionRunItem,
  ConfiguredSourceItem,
  DepartmentInfo,
  EligibilityResponse,
  HomepageSectionGroup,
  SchemeChangeItem,
  SchemeDetail,
  SchemeItem,
  SchemeSummary,
} from './types';

const API_BASE = import.meta.env.VITE_API_URL || '';

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('mahaseva_admin_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchHealth(): Promise<{ status: string; service: string }> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error('Backend health check failed');
  return res.json();
}

export async function fetchSummary(): Promise<SchemeSummary> {
  const res = await fetch(`${API_BASE}/api/v1/schemes/summary`);
  if (!res.ok) throw new Error('Failed to fetch schemes summary');
  return res.json();
}

export async function fetchHomepageSections(): Promise<Record<string, HomepageSectionGroup>> {
  const res = await fetch(`${API_BASE}/api/v1/schemes/homepage-sections`);
  if (!res.ok) throw new Error('Failed to fetch homepage scheme sections');
  const data = await res.json();
  return data.sections || {};
}

export async function fetchDepartments(): Promise<DepartmentInfo[]> {
  const res = await fetch(`${API_BASE}/api/v1/schemes/departments`);
  if (!res.ok) throw new Error('Failed to fetch departments');
  const data = await res.json();
  return data.departments || [];
}

export async function fetchSchemes(params: {
  q?: string;
  department?: string;
  category?: string;
  verification_status?: string;
  deadline_status?: string;
  provider_classification?: string;
  application_mode?: string;
  sort_by?: string;
  limit?: number;
  offset?: number;
}): Promise<{ total: number; limit: number; offset: number; items: SchemeItem[] }> {
  const query = new URLSearchParams();
  if (params.q) query.set('q', params.q);
  if (params.department) query.set('department', params.department);
  if (params.category) query.set('category', params.category);
  if (params.verification_status) query.set('verification_status', params.verification_status);
  if (params.deadline_status) query.set('deadline_status', params.deadline_status);
  if (params.provider_classification) query.set('provider_classification', params.provider_classification);
  if (params.application_mode) query.set('application_mode', params.application_mode);
  if (params.sort_by) query.set('sort_by', params.sort_by);
  query.set('limit', String(params.limit || 20));
  query.set('offset', String(params.offset || 0));

  const res = await fetch(`${API_BASE}/api/v1/schemes?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to query schemes');
  return res.json();
}

export async function fetchSchemeDetail(schemeId: number): Promise<SchemeDetail> {
  const res = await fetch(`${API_BASE}/api/v1/schemes/${schemeId}`);
  if (!res.ok) {
    if (res.status === 404) throw new Error('Scheme record not found');
    throw new Error('Failed to load scheme details');
  }
  return res.json();
}

export async function askAI(query: string, limit = 4): Promise<AIResponse> {
  const res = await fetch(`${API_BASE}/api/v1/ai/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'AI Assistant service unavailable');
  }
  return res.json();
}

export async function fetchCategories(): Promise<CategoryInfo[]> {
  const res = await fetch(`${API_BASE}/api/v1/schemes/categories`);
  if (!res.ok) throw new Error('Failed to fetch categories');
  const data = await res.json();
  return data.categories || [];
}

export async function askSchemeContextual(schemeId: number, query: string): Promise<AIResponse> {
  const res = await fetch(`${API_BASE}/api/v1/ai/scheme-chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scheme_id: schemeId, query }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Contextual AI assistance unavailable');
  }
  return res.json();
}

export async function chatAI(
  query: string,
  schemeId?: number,
  conversationHistory?: Array<{ role: string; content: string }>,
  lang?: string
): Promise<AIResponse> {
  const res = await fetch(`${API_BASE}/api/v1/ai/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      scheme_id: schemeId || undefined,
      conversation_history: conversationHistory || undefined,
      lang: lang || undefined,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'AI Assistant service unavailable');
  }
  return res.json();
}

export async function fetchApplicationGuide(schemeId: number): Promise<ApplicationGuideResponse> {
  const res = await fetch(`${API_BASE}/api/v1/schemes/${schemeId}/application-guide`);
  if (!res.ok) throw new Error('Failed to fetch application guide');
  return res.json();
}

export async function evaluateEligibility(
  schemeId: number,
  userInput: string,
  lang?: string
): Promise<EligibilityResponse> {
  const res = await fetch(`${API_BASE}/api/v1/ai/eligibility`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scheme_id: schemeId,
      user_input: userInput,
      lang: lang || undefined,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to evaluate eligibility');
  }
  return res.json();
}

export async function fetchConfiguredSources(): Promise<ConfiguredSourceItem[]> {
  const res = await fetch(`${API_BASE}/api/v1/sources`);
  if (!res.ok) throw new Error('Failed to fetch source registries');
  const data = await res.json();
  return data.sources || [];
}

// ---------------- Admin APIs ----------------

export async function adminLogin(
  username: string,
  password: string
): Promise<{ access_token: string; username: string; role: string }> {
  const res = await fetch(`${API_BASE}/api/v1/admin/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid username or password');
  }
  return res.json();
}

export async function fetchAdminProfile(): Promise<AdminUser> {
  const res = await fetch(`${API_BASE}/api/v1/admin/auth/me`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Admin session expired');
  return res.json();
}

export async function reviewScheme(
  schemeId: number,
  payload: {
    verification_status: string;
    notes?: string;
    brief_description?: string;
    benefits?: string;
    eligibility?: string;
    documents_required?: string;
    application_process?: string;
    official_apply_url?: string;
    category?: string;
    application_start_date?: string;
    application_deadline?: string;
    closing_time?: string;
    current_window_status?: string;
  }
): Promise<{ message: string; candidate: any }> {
  const res = await fetch(`${API_BASE}/api/v1/admin/schemes/${schemeId}/review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Review update failed');
  }
  return res.json();
}

export async function fetchSchemeChanges(reviewStatus?: string): Promise<SchemeChangeItem[]> {
  const url = reviewStatus
    ? `${API_BASE}/api/v1/admin/changes?review_status=${reviewStatus}`
    : `${API_BASE}/api/v1/admin/changes`;
  const res = await fetch(url, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch scheme changes');
  const data = await res.json();
  return data.items || [];
}

export async function reviewSchemeChange(
  changeId: number,
  reviewStatus: 'approved' | 'rejected',
  reviewNotes = ''
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/admin/changes/${changeId}/review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ review_status: reviewStatus, review_notes: reviewNotes }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to review change');
  }
  return res.json();
}

export async function fetchMonitoringStats(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/admin/monitoring/stats`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch monitoring stats');
  return res.json();
}

export async function triggerMonitoringScan(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/admin/monitoring/trigger`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to trigger scan');
  }
  return res.json();
}

export async function fetchAuditLogs(candidateId?: number): Promise<AuditLogItem[]> {
  const url = candidateId
    ? `${API_BASE}/api/v1/admin/audit-logs?candidate_id=${candidateId}`
    : `${API_BASE}/api/v1/admin/audit-logs`;
  const res = await fetch(url, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('Failed to fetch audit logs');
  const data = await res.json();
  return data.items || [];
}

export async function fetchCollectionRuns(): Promise<CollectionRunItem[]> {
  const res = await fetch(`${API_BASE}/api/v1/admin/collection-runs`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch collection runs');
  const data = await res.json();
  return data.runs || [];
}

export async function triggerCollectionSync(): Promise<{ message: string; timestamp_utc: string }> {
  const res = await fetch(`${API_BASE}/api/v1/admin/collection-runs/trigger`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to trigger collection sync');
  }
  return res.json();
}
