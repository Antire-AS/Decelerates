/**
 * API client — all calls go through /api/* which next.config.ts rewrites
 * to the FastAPI backend. Server-side calls (in Server Components / Route
 * Handlers) use the raw API_BASE_URL env var to skip the rewrite loop.
 */

const API_BASE =
  typeof window === "undefined"
    ? (process.env.API_BASE_URL ?? "http://localhost:8000")
    : "/bapi";

// Module-level token — set by the SessionSync component in providers.tsx
let _authToken: string | undefined;
export function setApiToken(token: string | undefined) {
  _authToken = token;
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(_authToken ? { Authorization: `Bearer ${_authToken}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${url}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface SearchResult {
  orgnr: string;
  navn: string;
  organisasjonsform?: string;
  kommune?: string;
  postnummer?: string;
  naeringskode1?: string;
  naeringskode1_beskrivelse?: string;
}

export interface OrgProfile {
  org: Record<string, unknown>;
  regnskap: Record<string, unknown>;
  risk: {
    score?: number;
    reasons?: string[];
    equity_ratio?: number;
  };
  pep: Record<string, unknown>;
  risk_summary: Record<string, unknown>;
}

export interface DashboardData {
  renewals_30d: number;
  renewals_90d: number;
  total_active_policies: number;
  open_claims: number;
  activities_due: number;
  total_premium_book: number;
  premium_at_risk_30d: number;
  recent_activities: Activity[];
}

export interface Activity {
  id: number;
  subject: string;
  type: string;
  completed: boolean;
  orgnr?: string;
  created_by?: string;
  due_date?: string;
}

export interface Company {
  orgnr: string;
  navn?: string;
  risk_score?: number;
  naeringskode1_beskrivelse?: string;
  kommune?: string;
}

export interface SlaAgreement {
  id: number;
  client_orgnr: string;
  client_name: string;
  created_at: string;
  start_date?: string;
  status?: string;
  signed_at?: string;
  signed_by?: string;
  insurance_lines?: string[];
  pdf_url?: string;
}

export interface HistoryRow {
  year: number;
  revenue?: number;
  total_assets?: number;
  equity_ratio?: number;
  source?: string;
  // BRREG fields
  sumDriftsinntekter?: number;
  arsresultat?: number;
  sumEgenkapital?: number;
  sumEiendeler?: number;
  [key: string]: unknown;
}

export interface Policy {
  id: number;
  orgnr: string;
  insurance_type: string;
  insurer: string;
  product_type?: string;
  policy_number?: string;
  annual_premium_nok?: number;
  coverage_amount_nok?: number;
  start_date?: string;
  renewal_date?: string;
  status: string;
  document_url?: string;
  notes?: string;
}

export interface Contact {
  id: number;
  orgnr: string;
  name: string;
  title?: string;
  email?: string;
  phone?: string;
  is_primary?: boolean;
  notes?: string;
}

export interface Claim {
  id: number;
  orgnr: string;
  policy_id?: number;
  claim_number?: string;
  status: string;
  incident_date?: string;
  reported_date?: string;
  estimated_amount_nok?: number;
  settled_amount_nok?: number;
  insurer_contact?: string;
  description?: string;
  notes?: string;
}

export interface ActivityItem {
  id: number;
  orgnr?: string;
  activity_type: string;
  subject: string;
  body?: string;
  due_date?: string;
  completed: boolean;
  created_at: string;
  created_by_email?: string;
}

export interface InsuranceOffer {
  id: number;
  orgnr: string;
  insurer_name: string;
  filename: string;
  uploaded_at: string;
  status?: string;
}

export interface InsuranceNeed {
  type: string;
  priority: string;
  estimated_coverage_nok?: number;
  estimated_annual_premium_nok?: { low: number; mid: number; high: number };
  reason: string;
}

export interface User {
  id: number;
  name?: string;
  email: string;
  role: string;
}

export interface Renewal {
  id: number;
  orgnr: string;
  client_name: string;
  insurance_type: string;
  insurer: string;
  premium: number;
  renewal_date: string;
  days_until_renewal: number;
  status: string;
  renewal_stage?: string;
  policy_number?: string;
  annual_premium_nok?: number;
  product_type?: string;
}

export interface PremiumAnalytics {
  total_premium_book: number;
  active_policy_count: number;
  renewals_90d_premium: number;
  avg_premium_per_policy: number;
  by_insurer: { insurer: string; count: number; total_premium: number; share_pct: number }[];
  by_product: { product_type: string; count: number; total_premium: number; share_pct: number }[];
  by_status: { status: string; count: number; total_premium: number; share_pct: number }[];
}

export interface PortfolioRiskRow {
  orgnr: string;
  navn?: string;
  revenue?: number;
  equity?: number;
  equity_ratio?: number;
  risk_score?: number;
  naeringskode?: string;
  regnskapsår?: number;
}

export interface InsuranceDocument {
  id: number;
  orgnr: string;
  filename: string;
  tags?: string[];
  created_at: string;
}

// ── Search / Company ──────────────────────────────────────────────────────────

export const searchCompanies = (name: string, size = 20, kommunenummer?: string) => {
  const params = new URLSearchParams({ name, size: String(size) });
  if (kommunenummer) params.set("kommunenummer", kommunenummer);
  return apiFetch<SearchResult[]>(`/search?${params}`);
};

export const getOrgProfile = (orgnr: string) =>
  apiFetch<OrgProfile>(`/org/${orgnr}`);

export const getOrgLicenses = (orgnr: string) =>
  apiFetch<unknown>(`/org/${orgnr}/licenses`);

export const getOrgRoles = (orgnr: string) =>
  apiFetch<unknown>(`/org/${orgnr}/roles`);

export const getOrgHistory = (orgnr: string) =>
  apiFetch<HistoryRow[]>(`/org/${orgnr}/history`);

export const getOrgBankruptcy = (orgnr: string) =>
  apiFetch<unknown>(`/org/${orgnr}/bankruptcy`);

export const getOrgStruktur = (orgnr: string) =>
  apiFetch<unknown>(`/org/${orgnr}/struktur`);

export const getOrgKoordinater = (orgnr: string) =>
  apiFetch<unknown>(`/org/${orgnr}/koordinater`);

export const getOrgBenchmark = (orgnr: string) =>
  apiFetch<unknown>(`/org/${orgnr}/benchmark`);

export const getCompanies = (limit = 20, sort_by = "navn") =>
  apiFetch<Company[]>(`/companies?limit=${limit}&sort_by=${sort_by}`);

// ── Dashboard ─────────────────────────────────────────────────────────────────

export const getDashboard = () => apiFetch<DashboardData>("/dashboard");

// ── CRM ───────────────────────────────────────────────────────────────────────

export const getOrgPolicies = (orgnr: string) =>
  apiFetch<Policy[]>(`/org/${orgnr}/policies`);

export const getOrgContacts = (orgnr: string) =>
  apiFetch<Contact[]>(`/org/${orgnr}/contacts`);

export const createContact = (orgnr: string, data: Omit<Contact, "id" | "orgnr">) =>
  apiFetch<Contact>(`/org/${orgnr}/contacts`, { method: "POST", body: JSON.stringify(data) });

export const deleteContact = (orgnr: string, id: number) =>
  apiFetch<void>(`/org/${orgnr}/contacts/${id}`, { method: "DELETE" });

export const createPolicy = (orgnr: string, data: Omit<Policy, "id" | "orgnr">) =>
  apiFetch<Policy>(`/org/${orgnr}/policies`, { method: "POST", body: JSON.stringify(data) });

export const deletePolicy = (orgnr: string, id: number) =>
  apiFetch<void>(`/org/${orgnr}/policies/${id}`, { method: "DELETE" });

export const getOrgClaims = (orgnr: string) =>
  apiFetch<Claim[]>(`/org/${orgnr}/claims`);

export const createClaim = (orgnr: string, data: Omit<Claim, "id" | "orgnr">) =>
  apiFetch<Claim>(`/org/${orgnr}/claims`, { method: "POST", body: JSON.stringify(data) });

export const deleteClaim = (orgnr: string, id: number) =>
  apiFetch<void>(`/org/${orgnr}/claims/${id}`, { method: "DELETE" });

export const getOrgActivities = (orgnr: string) =>
  apiFetch<ActivityItem[]>(`/org/${orgnr}/activities`);

export const createActivity = (orgnr: string, data: Record<string, unknown>) =>
  apiFetch<ActivityItem>(`/org/${orgnr}/activities`, { method: "POST", body: JSON.stringify(data) });

export const completeActivity = (orgnr: string, id: number) =>
  apiFetch<void>(`/org/${orgnr}/activities/${id}`, { method: "PUT", body: JSON.stringify({ completed: true }) });

export const deleteActivity = (orgnr: string, id: number) =>
  apiFetch<void>(`/org/${orgnr}/activities/${id}`, { method: "DELETE" });

// ── Portfolio ─────────────────────────────────────────────────────────────────

export const getPortfolioOverview = () =>
  apiFetch<unknown>("/portfolio/overview");

export interface PortfolioItem {
  id: number;
  name: string;
  description?: string;
  created_at: string;
}

export const getPortfolios = () => apiFetch<PortfolioItem[]>("/portfolio");

export const createPortfolio = (name: string, description = "") =>
  apiFetch<PortfolioItem>("/portfolio", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });

export const portfolioChat = (portfolioId: number, question: string) =>
  apiFetch<{ answer: string; sources: string[] }>(`/portfolio/${portfolioId}/chat`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });

export const seedFullDemo = () =>
  apiFetch<{
    companies_created: number;
    history_rows_created: number;
    policies_created: number;
    message: string;
  }>("/admin/seed-full-demo", { method: "POST" });

// ── Renewals ─────────────────────────────────────────────────────────────────

export const getRenewals = (days?: number) => {
  const q = days ? `?days=${days}` : "";
  return apiFetch<Renewal[]>(`/renewals${q}`);
};

// ── SLA ───────────────────────────────────────────────────────────────────────

export const getSlaAgreements = () =>
  apiFetch<SlaAgreement[]>("/sla");

export const createSlaAgreement = (data: Record<string, unknown>) =>
  apiFetch<SlaAgreement>("/sla", {
    method: "POST",
    body: JSON.stringify(data),
  });

// ── Documents ────────────────────────────────────────────────────────────────

export const getInsuranceDocuments = (orgnr?: string) => {
  const q = orgnr ? `?orgnr=${orgnr}` : "";
  return apiFetch<InsuranceDocument[]>(`/insurance-documents${q}`);
};

export const deleteInsuranceDocument = (id: number) =>
  apiFetch<void>(`/insurance-documents/${id}`, { method: "DELETE" });

export const compareInsuranceDocuments = (docIds: [number, number]) =>
  apiFetch<{ comparison: string; docs: string[] }>("/insurance-documents/compare", {
    method: "POST",
    body: JSON.stringify({ doc_ids: docIds }),
  });

export const chatWithInsuranceDocument = (id: number, question: string, orgnr?: string) =>
  apiFetch<{ answer: string }>(`/insurance-documents/${id}/chat`, {
    method: "POST",
    body: JSON.stringify({ question, orgnr }),
  });

export async function uploadInsuranceDocument(
  file: File,
  opts: { orgnr?: string; title?: string; tags?: string } = {},
): Promise<InsuranceDocument> {
  const fd = new FormData();
  fd.append("file", file);
  if (opts.orgnr) fd.append("orgnr", opts.orgnr);
  if (opts.title) fd.append("title", opts.title);
  if (opts.tags)  fd.append("tags",  opts.tags);
  const base = typeof window === "undefined"
    ? (process.env.API_BASE_URL ?? "http://localhost:8000") : "/bapi";
  const res = await fetch(`${base}/insurance-documents`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function downloadInsuranceDocumentPdf(id: number, filename: string): Promise<void> {
  const res = await fetch(`/bapi/insurance-documents/${id}/pdf`);
  if (!res.ok) throw new Error(`PDF download failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ── Knowledge ────────────────────────────────────────────────────────────────

export const knowledgeChat = (question: string, orgnr?: string) =>
  apiFetch<{ answer: string; sources?: string[]; source_snippets?: Record<string, string> }>("/knowledge/chat", {
    method: "POST",
    body: JSON.stringify({ question, orgnr }),
  });

export const getKnowledgeStats = () =>
  apiFetch<{ total_chunks: number; doc_chunks: number; video_chunks: number }>("/knowledge/index/stats");

// ── Videos ───────────────────────────────────────────────────────────────────

export const getVideos = () => apiFetch<unknown[]>("/videos");

export async function uploadVideo(file: File): Promise<{ url: string; name: string }> {
  const fd = new FormData();
  fd.append("file", file);
  const base = typeof window === "undefined"
    ? (process.env.API_BASE_URL ?? "http://localhost:8000") : "/bapi";
  const res = await fetch(`${base}/videos/upload`, {
    method: "POST",
    body: fd,
    headers: _authToken ? { Authorization: `Bearer ${_authToken}` } : {},
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

// ── Analytics ────────────────────────────────────────────────────────────────

export const getPremiumAnalytics = () =>
  apiFetch<PremiumAnalytics>("/analytics/premiums");

export const getPortfolioRisk = (id: number) =>
  apiFetch<PortfolioRiskRow[]>(`/portfolio/${id}/risk`);

// ── Renewal stage ─────────────────────────────────────────────────────────────

export const advanceRenewalStage = (policyId: number, stage: string, notifyEmail?: string) =>
  apiFetch<void>(`/policies/${policyId}/renewal/advance`, {
    method: "POST",
    body: JSON.stringify({ stage, ...(notifyEmail ? { notify_email: notifyEmail } : {}) }),
  });

// ── Forsikring / offers ──────────────────────────────────────────────────────

export const getOrgInsuranceNeeds = (orgnr: string) =>
  apiFetch<{ narrative?: string; needs: InsuranceNeed[] }>(`/org/${orgnr}/insurance-needs`);

export const generateRiskOffer = (orgnr: string, lang = "no") =>
  apiFetch<{ sammendrag?: string; anbefalinger?: unknown[]; total_premieanslag?: string }>(
    `/org/${orgnr}/risk-offer?lang=${lang}`, { method: "POST" },
  );

export const generateNarrative = (orgnr: string, lang = "no") =>
  apiFetch<{ narrative: string }>(`/org/${orgnr}/narrative?lang=${lang}`, { method: "POST" });

export const getOrgOffers = (orgnr: string) =>
  apiFetch<InsuranceOffer[]>(`/org/${orgnr}/offers`);

export const updateOfferStatus = (orgnr: string, id: number, status: string) =>
  apiFetch<void>(`/org/${orgnr}/offers/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });

export const deleteOffer = (orgnr: string, id: number) =>
  apiFetch<void>(`/org/${orgnr}/offers/${id}`, { method: "DELETE" });

export const createClientToken = (orgnr: string, label?: string) => {
  const q = label ? `?label=${encodeURIComponent(label)}` : "";
  return apiFetch<{ token: string }>(`/org/${orgnr}/client-token${q}`, { method: "POST" });
};

export const getClientTokens = (orgnr: string) =>
  apiFetch<{ token: string; label?: string; expires_at: string }[]>(`/org/${orgnr}/client-tokens`);

// ── Admin ─────────────────────────────────────────────────────────────────────

export const getAdminStats = () => apiFetch<unknown>("/admin/stats");

export const getUsers = () => apiFetch<User[]>("/users");

export const updateUserRole = (id: number, role: string) =>
  apiFetch<void>(`/users/${id}/role`, { method: "PUT", body: JSON.stringify({ role }) });

export const getAuditLog = (limit = 50) =>
  apiFetch<unknown[]>(`/audit?limit=${limit}`);

export const getPolicies = () => apiFetch<Policy[]>("/policies");

export const seedCrmDemo = () =>
  apiFetch<{ policies_created: number; claims_created: number; activities_created: number }>(
    "/admin/seed-crm-demo", { method: "POST" },
  );

export const seedDemoDocuments = () =>
  apiFetch<{ created: number; skipped: number; reason?: string }>(
    "/admin/seed-demo-documents", { method: "POST" },
  );

export const loadDemo = () =>
  apiFetch<{ portfolio_name: string; companies: number }>("/admin/demo", { method: "POST" });

export const resetData = () =>
  apiFetch<void>("/admin/reset", { method: "DELETE" });

export const seedNorwayTop100 = () =>
  apiFetch<{ portfolio_name: string; pdf_agent_queued: number }>(
    "/admin/seed-norway-top100", { method: "POST" },
  );

export const sendPortfolioDigest = () =>
  apiFetch<{ recipient: string; emails_sent: number; portfolios_checked: number }>(
    "/admin/portfolio-digest", { method: "POST" },
  );

export const sendActivityReminders = () =>
  apiFetch<{ sent: boolean; recipient?: string; overdue?: number; due_today?: number }>(
    "/admin/activity-reminders", { method: "POST" },
  );

export const sendRenewalThresholdEmails = () =>
  apiFetch<{ recipient: string; total_notifications_sent: number; thresholds_checked: { threshold_days: number; policies_found: number }[] }>(
    "/admin/renewal-threshold-emails", { method: "POST" },
  );

// ── Document extras ───────────────────────────────────────────────────────────

export const getDocumentKeyPoints = (id: number) =>
  apiFetch<Record<string, unknown>>(`/insurance-documents/${id}/keypoints`);

export const getSimilarDocuments = (id: number) =>
  apiFetch<InsuranceDocument[]>(`/insurance-documents/${id}/similar`);

// ── Portfolio extras ──────────────────────────────────────────────────────────

export const getPortfolioAlerts = (portfolioId: number) =>
  apiFetch<{ orgnr: string; navn?: string; severity: string; message: string; year?: number }[]>(
    `/portfolio/${portfolioId}/alerts`,
  );

export const getPortfolioConcentration = (portfolioId: number) =>
  apiFetch<{
    industry: { label: string; count: number }[];
    geography: { label: string; count: number }[];
    size: { label: string; count: number }[];
  }>(`/portfolio/${portfolioId}/concentration`);

export const removePortfolioCompany = (portfolioId: number, orgnr: string) =>
  apiFetch<void>(`/portfolio/${portfolioId}/companies/${orgnr}`, { method: "DELETE" });

export async function downloadPortfolioPdf(portfolioId: number, name: string): Promise<void> {
  const res = await fetch(`/bapi/portfolio/${portfolioId}/pdf`);
  if (!res.ok) throw new Error(`PDF download failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `portefolje_${name.replace(/\s+/g, "_")}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Org financial extras ──────────────────────────────────────────────────────

export const getOrgExtractionStatus = (orgnr: string) =>
  apiFetch<{
    status: string;
    source_years: number[];
    done_years: number[];
    pending_years: number[];
    missing_target_years: number[];
  }>(`/org/${orgnr}/extraction-status`);

export const getOrgFinancialCommentary = (orgnr: string) =>
  apiFetch<{ commentary: string; years_analyzed: number }>(`/org/${orgnr}/financial-commentary`);

// ── Broker notes (per company) ────────────────────────────────────────────────

export interface BrokerNote {
  id: number;
  text: string;
  created_at: string;
}

export const getOrgBrokerNotes = (orgnr: string) =>
  apiFetch<BrokerNote[]>(`/org/${orgnr}/broker-notes`);

export const createOrgBrokerNote = (orgnr: string, text: string) =>
  apiFetch<{ id: number; created_at: string }>(`/org/${orgnr}/broker-notes`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });

export const deleteOrgBrokerNote = (orgnr: string, id: number) =>
  apiFetch<void>(`/org/${orgnr}/broker-notes/${id}`, { method: "DELETE" });

// ── PDF history (add annual report URL) ──────────────────────────────────────

export const addOrgPdfHistory = (
  orgnr: string,
  data: { pdf_url: string; year: number; label?: string },
) =>
  apiFetch<{ orgnr: string; extracted: unknown }>(`/org/${orgnr}/pdf-history`, {
    method: "POST",
    body: JSON.stringify({ pdf_url: data.pdf_url, year: data.year, label: data.label ?? "" }),
  });

// ── Company-specific RAG chat ─────────────────────────────────────────────────

export const chatWithOrg = (orgnr: string, question: string, session_id?: string) =>
  apiFetch<{ answer: string; session_id?: string }>(`/org/${orgnr}/chat`, {
    method: "POST",
    body: JSON.stringify({ question, ...(session_id ? { session_id } : {}) }),
  });

// ── Risk narrative ────────────────────────────────────────────────────────────

export const getRiskNarrative = (orgnr: string) =>
  apiFetch<{ narrative: string }>(`/org/${orgnr}/risk-narrative`);

// ── Broker settings ───────────────────────────────────────────────────────────

export const getBrokerSettings = () =>
  apiFetch<Record<string, string>>("/broker/settings");

export const saveBrokerSettings = (data: Record<string, string>) =>
  apiFetch<void>("/broker/settings", {
    method: "POST",
    body: JSON.stringify(data),
  });

// ── SLA extras ────────────────────────────────────────────────────────────────

export const signSlaAgreement = (id: number, signed_by: string) =>
  apiFetch<void>(`/sla/${id}/sign`, { method: "PATCH", body: JSON.stringify({ signed_by }) });

export async function downloadSlaPdf(id: number, filename: string): Promise<void> {
  const res = await fetch(`/bapi/sla/${id}/pdf`);
  if (!res.ok) throw new Error(`PDF download failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ── Offer upload (multipart) ──────────────────────────────────────────────────

export async function uploadOrgOffers(
  orgnr: string,
  files: File[],
): Promise<{ id: number; filename: string; insurer_name: string }[]> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  const base = typeof window === "undefined"
    ? (process.env.API_BASE_URL ?? "http://localhost:8000")
    : "/bapi";
  const res = await fetch(`${base}/org/${orgnr}/offers`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`API ${res.status}: upload offers`);
  return res.json();
}
