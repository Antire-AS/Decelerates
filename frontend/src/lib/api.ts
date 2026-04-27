/**
 * API client — all calls go through /api/* which next.config.ts rewrites
 * to the FastAPI backend. Server-side calls (in Server Components / Route
 * Handlers) use the raw API_BASE_URL env var to skip the rewrite loop.
 */

import type {
  SearchResult,
  OrgProfile,
  AltmanHistoryOut,
  DashboardData,
  Company,
  SlaAgreement,
  HistoryRow,
  Policy,
  Contact,
  Claim,
  ActivityItem,
  InsuranceOffer,
  InsuranceNeed,
  User,
  Renewal,
  PremiumAnalytics,
  PortfolioRiskRow,
  InsuranceDocument,
  PortfolioItem,
  BrokerNote,
  CommissionAnalytics,
  IddBehovsanalyse,
  ClientToken,
  ClientPortalProfile,
  Insurer,
  Submission,
  Recommendation,
  CoverageGap,
} from "./api-types";

export type {
  SearchResult,
  OrgProfile,
  RiskFactor,
  AltmanZScore,
  DashboardData,
  Activity,
  Company,
  SlaAgreement,
  HistoryRow,
  Policy,
  Contact,
  Claim,
  ActivityItem,
  InsuranceOffer,
  InsuranceNeed,
  User,
  Renewal,
  PremiumAnalytics,
  PortfolioRiskRow,
  InsuranceDocument,
  PortfolioItem,
  BrokerNote,
  CommissionAnalytics,
  IddBehovsanalyse,
  ClientToken,
  ClientPortalProfile,
  Insurer,
  Submission,
  Recommendation,
  CoverageGap,
  CoverageGapItem,
} from "./api-types";

import { downloadFile, apiBaseUrl } from "./api-utils";
import type { components } from "./api-schema";

// Aliases for generated schema types — re-exported here so callers can do
// `import { BankruptcyOut } from "@/lib/api"`. To regenerate after a backend
// change, run `npm run gen:api-types` from frontend/.
type Schema = components["schemas"];
export type BankruptcyOut       = Schema["BankruptcyOut"];
export type BoardMembersOut     = Schema["BoardMembersOut"];
export type BoardMember         = Schema["BoardMember"];
export type LicensesOut         = Schema["LicensesOut"];
export type LicenseItem         = Schema["LicenseItem"];
export type KoordinaterOut      = Schema["KoordinaterOut"];
export type StrukturOut         = Schema["StrukturOut"];
export type BenchmarkOut        = Schema["BenchmarkOut"];
export type PeerBenchmarkOut    = Schema["PeerBenchmarkOut"];
export type HistoryOut          = Schema["HistoryOut"];
export type HistoryRowOut       = Schema["HistoryRowOut"];
export type ExtractionStatusOut = Schema["ExtractionStatusOut"];
export type PdfHistoryOut       = Schema["PdfHistoryOut"];
export type EstimateOut         = Schema["EstimateOut"];
export type KnowledgeStatsOut   = Schema["KnowledgeStatsOut"];
export type KnowledgeIndexOut   = Schema["KnowledgeIndexOut"];
export type RiskOfferOut        = Schema["RiskOfferOut"];
export type NarrativeOut        = Schema["NarrativeOut"];
export type KnowledgeChatOut    = Schema["KnowledgeChatOut"];
export type OrgChatOut          = Schema["OrgChatOut"];
export type DocumentChatOut     = Schema["DocumentChatOut"];
export type DocumentCompareOut  = Schema["DocumentCompareOut"];
export type DocumentKeypointsOut = Schema["DocumentKeypointsOut"];

// Deal pipeline (plan §🟢 #9). Every endpoint declares response_model on the
// backend, so these are exact contract aliases — never an inline shape.
export type PipelineStageOut    = Schema["PipelineStageOut"];
export type PipelineStageCreate = Schema["PipelineStageCreate"];
export type PipelineStageUpdate = Schema["PipelineStageUpdate"];
export type DealOut             = Schema["DealOut"];
export type DealCreate          = Schema["DealCreate"];
export type DealUpdate          = Schema["DealUpdate"];
export type DealStageChange     = Schema["DealStageChange"];
export type DealLose            = Schema["DealLose"];

// Notifications inbox (plan §🟢 #17).
export type NotificationOut         = Schema["NotificationOut"];
export type NotificationListOut     = Schema["NotificationListOut"];
export type NotificationMarkReadOut = Schema["NotificationMarkReadOut"];

// Audit log UI (plan §🟢 #13).
export type AuditLogEntryOut = Schema["AuditLogEntryOut"];
export type AuditLogPageOut  = Schema["AuditLogPageOut"];

// Inbound-email audit log (msgraph activation Task 11).
export type IncomingEmailLogEntryOut = Schema["IncomingEmailLogEntryOut"];
export type IncomingEmailLogPageOut  = Schema["IncomingEmailLogPageOut"];

// Commission projections (plan §🟢 #12).
export type CommissionProjectionBucket = Schema["CommissionProjectionBucket"];
export type CommissionProjectionsOut   = Schema["CommissionProjectionsOut"];

// Bulk operations (plan §🟢 #18).
export type PortfolioBulkAdd       = Schema["PortfolioBulkAdd"];
export type PortfolioBulkAddOut    = Schema["PortfolioBulkAddOut"];
export type ActivityBulkComplete   = Schema["ActivityBulkComplete"];
export type ActivityBulkCompleteOut = Schema["ActivityBulkCompleteOut"];

// Saved searches (plan §🟢 #19).
export type SavedSearchOut    = Schema["SavedSearchOut"];
export type SavedSearchCreate = Schema["SavedSearchCreate"];

// Email compose (plan §🟢 #10).
export type EmailComposeIn  = Schema["EmailComposeIn"];
export type EmailComposeOut = Schema["EmailComposeOut"];

// Signicat e-sign (plan §🟢 #11).
export type SigningSessionOut = Schema["SigningSessionOut"];

const API_BASE = apiBaseUrl();

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

// ── Search / Company ──────────────────────────────────────────────────────────

export const searchCompanies = (name: string, size = 20, kommunenummer?: string) => {
  const params = new URLSearchParams({ name, size: String(size) });
  if (kommunenummer) params.set("kommunenummer", kommunenummer);
  return apiFetch<SearchResult[]>(`/search?${params}`);
};

export const getOrgProfile = (orgnr: string) =>
  apiFetch<OrgProfile>(`/org/${orgnr}`);

export const getOrgLicenses = (orgnr: string) =>
  apiFetch<LicensesOut>(`/org/${orgnr}/licenses`);

export const getOrgRoles = (orgnr: string) =>
  apiFetch<BoardMembersOut>(`/org/${orgnr}/roles`);

export const getOrgHistory = (orgnr: string) =>
  apiFetch<HistoryOut>(`/org/${orgnr}/history`)
    .then((r) => (r.years ?? []) as unknown as HistoryRow[]);

export const getOrgAltmanHistory = (orgnr: string) =>
  apiFetch<AltmanHistoryOut>(`/org/${orgnr}/altman-history`);

export type CompanyNewsOut = Schema["CompanyNewsOut"];
export type CompanyNewsItem = Schema["CompanyNewsItem"];
export type CompanyNewsRefreshOut = Schema["CompanyNewsRefreshOut"];

export const getOrgNews = (orgnr: string, onlyMaterial = false) => {
  const qs = onlyMaterial ? "?only_material=true" : "";
  return apiFetch<CompanyNewsOut>(`/org/${orgnr}/news${qs}`);
};

export const refreshOrgNews = (orgnr: string) =>
  apiFetch<CompanyNewsRefreshOut>(`/org/${orgnr}/news/refresh`, { method: "POST" });

export const getOrgBankruptcy = (orgnr: string) =>
  apiFetch<BankruptcyOut>(`/org/${orgnr}/bankruptcy`);

export const getOrgStruktur = (orgnr: string) =>
  apiFetch<StrukturOut>(`/org/${orgnr}/struktur`);

export const getOrgKoordinater = (orgnr: string) =>
  apiFetch<KoordinaterOut>(`/org/${orgnr}/koordinater`);

export const getOrgBenchmark = (orgnr: string) =>
  apiFetch<BenchmarkOut>(`/org/${orgnr}/benchmark`);

export const getOrgPeerBenchmark = (orgnr: string) =>
  apiFetch<PeerBenchmarkOut>(`/org/${orgnr}/peer-benchmark`);

export const getOrgEstimate = (orgnr: string) =>
  apiFetch<EstimateOut>(`/org/${orgnr}/estimate`);

export const getExchangeRate = (currency: string) =>
  apiFetch<{ currency: string; nok_rate: number }>(`/norgesbank/rate/${currency}`);

export const deleteOrgHistory = (orgnr: string) =>
  apiFetch<{ deleted_rows: number }>(`/org/${orgnr}/history`, { method: "DELETE" });

export const getCompanies = (
  limit = 20,
  sort_by = "navn",
  opts: {
    nace_section?: string;
    min_revenue?: number;
    max_revenue?: number;
    min_risk?: number;
    max_risk?: number;
    kommune?: string;
  } = {},
) => {
  const params = new URLSearchParams({ limit: String(limit), sort_by });
  if (opts.nace_section) params.set("nace_section", opts.nace_section);
  if (opts.min_revenue != null) params.set("min_revenue", String(opts.min_revenue));
  if (opts.max_revenue != null) params.set("max_revenue", String(opts.max_revenue));
  if (opts.min_risk != null)    params.set("min_risk",    String(opts.min_risk));
  if (opts.max_risk != null)    params.set("max_risk",    String(opts.max_risk));
  if (opts.kommune) params.set("kommune", opts.kommune);
  return apiFetch<Company[]>(`/companies?${params}`);
};

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

export const getPortfolios = () => apiFetch<PortfolioItem[]>("/portfolio");

export const getPortfolio = (id: number) => apiFetch<PortfolioItem>(`/portfolio/${id}`);

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
  apiFetch<DocumentCompareOut>("/insurance-documents/compare", {
    method: "POST",
    body: JSON.stringify({ doc_ids: docIds }),
  });

export const chatWithInsuranceDocument = (id: number, question: string, orgnr?: string) =>
  apiFetch<DocumentChatOut>(`/insurance-documents/${id}/chat`, {
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
  const res = await fetch(`${apiBaseUrl()}/insurance-documents`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function downloadInsuranceDocumentPdf(id: number, filename: string): Promise<void> {
  await downloadFile(`/bapi/insurance-documents/${id}/pdf`, filename);
}

// ── Knowledge ────────────────────────────────────────────────────────────────

export const knowledgeChat = (question: string, orgnr?: string, signal?: AbortSignal, context?: string) =>
  apiFetch<KnowledgeChatOut>("/knowledge/chat", {
    method: "POST",
    body: JSON.stringify({ question, orgnr, context }),
    signal,
  });

export const knowledgeQuickUpload = async (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/bapi/knowledge/quick-upload", {
    method: "POST",
    body: fd,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as {
    doc_id: number;
    filename: string;
    chunks_indexed: number;
  };
};

// ── Chat history (per-user memory) ───────────────────────────────────────────

export type ChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
  created_at: string | null;
};

export const getChatHistory = (orgnr?: string) => {
  const qs = orgnr ? `?orgnr=${encodeURIComponent(orgnr)}` : "";
  return apiFetch<{ orgnr: string | null; messages: ChatHistoryMessage[] }>(
    `/chat/history${qs}`,
  );
};

export const clearChatHistory = (orgnr?: string) => {
  const qs = orgnr ? `?orgnr=${encodeURIComponent(orgnr)}` : "";
  return apiFetch<{ deleted: number }>(`/chat/history${qs}`, { method: "DELETE" });
};

// ── Whiteboard (per-user focus workspace per company) ────────────────────────

export type WhiteboardItem = {
  id: string;
  label: string;
  value: string;
  source_tab?: string;
};

export type WhiteboardOut = {
  orgnr: string;
  items: WhiteboardItem[];
  notes: string;
  ai_summary: string;
  updated_at: string | null;
};

export const getWhiteboard = (orgnr: string) =>
  apiFetch<WhiteboardOut>(`/org/${encodeURIComponent(orgnr)}/whiteboard`);

export const saveWhiteboard = (
  orgnr: string,
  body: { items: WhiteboardItem[]; notes: string },
) =>
  apiFetch<WhiteboardOut>(`/org/${encodeURIComponent(orgnr)}/whiteboard`, {
    method: "PUT",
    body: JSON.stringify(body),
  });

export const generateWhiteboardAiSummary = (orgnr: string) =>
  apiFetch<{ ai_summary: string }>(
    `/org/${encodeURIComponent(orgnr)}/whiteboard/ai-summary`,
    { method: "POST" },
  );

export const getKnowledgeStats = () =>
  apiFetch<KnowledgeStatsOut>("/knowledge/index/stats");

export const knowledgeSearch = (query: string, limit = 10) => {
  const params = new URLSearchParams({ query, limit: String(limit) });
  return apiFetch<Array<{ source: string; chunk_text: string; orgnr: string; created_at?: string }>>(
    `/knowledge?${params}`,
  );
};

export const knowledgeIndex = (force = false) =>
  apiFetch<KnowledgeIndexOut>(`/knowledge/index?force=${force}`, { method: "POST" });

export const knowledgeSeedRegulations = () =>
  apiFetch<{ seeded: Array<{ name: string; status: string; chunks?: number }> }>(
    "/knowledge/seed-regulations",
    { method: "POST" },
  );

export const knowledgeIngest = (orgnr: string, text: string, source = "custom_note") =>
  apiFetch<{ orgnr: string; chunks_stored: number }>(
    `/org/${orgnr}/ingest-knowledge`,
    { method: "POST", body: JSON.stringify({ text, source }) },
  );

// ── Videos ───────────────────────────────────────────────────────────────────

export const getVideos = () => apiFetch<unknown[]>("/videos");

export async function uploadVideo(file: File): Promise<{ url: string; name: string }> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${apiBaseUrl()}/videos/upload`, {
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

export type PortfolioAltmanRiskOut = Schema["PortfolioRiskSummaryOut"];
export type PortfolioAltmanRefreshOut = Schema["PortfolioRiskRefreshOut"];

export const getPortfolioAltmanRisk = (id: number) =>
  apiFetch<PortfolioAltmanRiskOut>(`/portfolio/${id}/altman-risk`);

export const refreshPortfolioAltmanRisk = (id: number) =>
  apiFetch<PortfolioAltmanRefreshOut>(`/portfolio/${id}/altman-risk/refresh`, {
    method: "POST",
  });

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
  apiFetch<RiskOfferOut>(`/org/${orgnr}/risk-offer?lang=${lang}`, { method: "POST" });

export const generateNarrative = (orgnr: string, lang = "no") =>
  apiFetch<NarrativeOut>(`/org/${orgnr}/narrative?lang=${lang}`, { method: "POST" });

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

export const getAdminStats = () => apiFetch<unknown>("/dashboard");

export const getUsers = () => apiFetch<User[]>("/users");

export const updateUserRole = (id: number, role: string) =>
  apiFetch<void>(`/users/${id}/role`, { method: "PUT", body: JSON.stringify({ role }) });

export const getAuditLog = (params?: {
  orgnr?: string;
  action?: string;
  actor_email?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}) => {
  const q = new URLSearchParams();
  if (params?.orgnr)       q.set("orgnr", params.orgnr);
  if (params?.action)      q.set("action", params.action);
  if (params?.actor_email) q.set("actor_email", params.actor_email);
  if (params?.from_date)   q.set("from_date", params.from_date);
  if (params?.to_date)     q.set("to_date", params.to_date);
  q.set("limit", String(params?.limit ?? 50));
  q.set("offset", String(params?.offset ?? 0));
  return apiFetch<AuditLogPageOut>(`/audit?${q.toString()}`);
};

export const getCommissionProjections = (months: number = 12) =>
  apiFetch<CommissionProjectionsOut>(`/commission/projections?months=${months}`);

export const getInboundEmailLog = (params?: {
  status?: "matched" | "orphaned" | "error" | "dedup";
  limit?: number;
  offset?: number;
}) => {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  q.set("limit", String(params?.limit ?? 50));
  q.set("offset", String(params?.offset ?? 0));
  return apiFetch<IncomingEmailLogPageOut>(`/admin/email-log?${q.toString()}`);
};

export type SeededTenderOut = {
  tender_id: number;
  url: string;
  orgnr: string;
  recipients: { insurer_name: string; insurer_email: string }[];
};

export const seedDemoTender = () =>
  apiFetch<SeededTenderOut>("/admin/seed-demo-tender", { method: "POST" });

export const addCompaniesBulk = (portfolioId: number, orgnrs: string[]) =>
  apiFetch<PortfolioBulkAddOut>(`/portfolio/${portfolioId}/companies/bulk`, {
    method: "POST",
    body: JSON.stringify({ orgnrs }),
  });

export const bulkCompleteActivities = (activityIds: number[]) =>
  apiFetch<ActivityBulkCompleteOut>("/activities/bulk-complete", {
    method: "POST",
    body: JSON.stringify({ activity_ids: activityIds }),
  });

// Saved searches (plan §🟢 #19) ─────────────────────────────────────────────

export const getSavedSearches = () =>
  apiFetch<SavedSearchOut[]>("/saved-searches");

export const createSavedSearch = (name: string, params: Record<string, unknown>) =>
  apiFetch<SavedSearchOut>("/saved-searches", {
    method: "POST",
    body: JSON.stringify({ name, params }),
  });

export const deleteSavedSearch = (searchId: number) =>
  apiFetch<void>(`/saved-searches/${searchId}`, { method: "DELETE" });

// Email compose (plan §🟢 #10) ──────────────────────────────────────────────

export const composeEmail = (data: EmailComposeIn) =>
  apiFetch<EmailComposeOut>("/email/compose", {
    method: "POST",
    body: JSON.stringify(data),
  });

// Signicat e-sign (plan §🟢 #11) ─────────────────────────────────────────────

export const signRecommendation = (orgnr: string, recId: number) =>
  apiFetch<SigningSessionOut>(`/org/${orgnr}/recommendations/${recId}/sign`, {
    method: "POST",
  });

export const getOrgAuditLog = (orgnr: string, params?: {
  action?: string;
  actor_email?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}) => {
  const q = new URLSearchParams();
  if (params?.action)      q.set("action", params.action);
  if (params?.actor_email) q.set("actor_email", params.actor_email);
  if (params?.from_date)   q.set("from_date", params.from_date);
  if (params?.to_date)     q.set("to_date", params.to_date);
  q.set("limit", String(params?.limit ?? 50));
  q.set("offset", String(params?.offset ?? 0));
  return apiFetch<AuditLogPageOut>(`/audit/${orgnr}?${q.toString()}`);
};

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
  apiFetch<DocumentKeypointsOut>(`/insurance-documents/${id}/keypoints`);

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
  await downloadFile(
    `/bapi/portfolio/${portfolioId}/pdf`,
    `portefolje_${name.replace(/\s+/g, "_")}.pdf`,
  );
}

// ── Org financial extras ──────────────────────────────────────────────────────

export const getOrgExtractionStatus = (orgnr: string) =>
  apiFetch<ExtractionStatusOut>(`/org/${orgnr}/extraction-status`);

export type FinancialCommentaryOut = Schema["FinancialCommentaryOut"];

export const getOrgFinancialCommentary = (orgnr: string) =>
  apiFetch<FinancialCommentaryOut>(`/org/${orgnr}/financial-commentary`);

// ── Broker notes (per company) ────────────────────────────────────────────────

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
  apiFetch<PdfHistoryOut>(`/org/${orgnr}/pdf-history`, {
    method: "POST",
    body: JSON.stringify({ pdf_url: data.pdf_url, year: data.year, label: data.label ?? "" }),
  });

// ── Company-specific RAG chat ─────────────────────────────────────────────────

export const chatWithOrg = (orgnr: string, question: string, session_id?: string, mode?: "rag" | "agent") => {
  const params = new URLSearchParams();
  if (session_id) params.set("session_id", session_id);
  if (mode) params.set("mode", mode);
  const qs = params.toString();
  return apiFetch<OrgChatOut & { tool_calls?: { tool: string; args: string; result: string }[] }>(
    `/org/${orgnr}/chat${qs ? `?${qs}` : ""}`,
    { method: "POST", body: JSON.stringify({ question }) },
  );
};

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
  await downloadFile(`/bapi/sla/${id}/pdf`, filename);
}

// ── Offer upload (multipart) ──────────────────────────────────────────────────

export async function uploadOrgOffers(
  orgnr: string,
  files: File[],
): Promise<{ id: number; filename: string; insurer_name: string }[]> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  const res = await fetch(`${apiBaseUrl()}/org/${orgnr}/offers`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`API ${res.status}: upload offers`);
  return res.json();
}

// ── Commission analytics ──────────────────────────────────────────────────────

export const getCommissionAnalytics = () =>
  apiFetch<CommissionAnalytics>("/analytics/commissions");

// ── IDD behovsanalyse ─────────────────────────────────────────────────────────

export const getOrgIdd = (orgnr: string) =>
  apiFetch<IddBehovsanalyse[]>(`/org/${orgnr}/idd`);

export const getAllIdd = (limit = 100) =>
  apiFetch<IddBehovsanalyse[]>(`/idd?limit=${limit}`);

export const createOrgIdd = (orgnr: string, body: Partial<IddBehovsanalyse>) =>
  apiFetch<IddBehovsanalyse>(`/org/${orgnr}/idd`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const deleteOrgIdd = (orgnr: string, iddId: number) =>
  apiFetch<void>(`/org/${orgnr}/idd/${iddId}`, { method: "DELETE" });

// ── Coverage gap ──────────────────────────────────────────────────────────────

export const getOrgCoverageGap = (orgnr: string) =>
  apiFetch<CoverageGap>(`/org/${orgnr}/coverage-gap`);

// ── Recommendations ───────────────────────────────────────────────────────────

export const getOrgRecommendations = (orgnr: string) =>
  apiFetch<Recommendation[]>(`/org/${orgnr}/recommendations`);

export const createRecommendation = (
  orgnr: string,
  data: { recommended_insurer: string; submission_ids?: number[]; idd_id?: number; rationale_text?: string },
) =>
  apiFetch<Recommendation>(`/org/${orgnr}/recommendations`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const downloadRecommendationPdf = (orgnr: string, recId: number) =>
  downloadFile(`/bapi/org/${orgnr}/recommendations/${recId}/pdf`, `anbefaling_${orgnr}_${recId}.pdf`);

export const deleteRecommendation = (orgnr: string, recId: number) =>
  apiFetch<void>(`/org/${orgnr}/recommendations/${recId}`, { method: "DELETE" });

// ── Certificate of Insurance ──────────────────────────────────────────────────

export const downloadCertificatePdf = (orgnr: string) =>
  downloadFile(`/bapi/org/${orgnr}/certificate/pdf`, `forsikringsbevis_${orgnr}.pdf`);

// ── Insurers ──────────────────────────────────────────────────────────────────

export const getInsurers = () =>
  apiFetch<Insurer[]>("/insurers");

export const createInsurer = (data: Omit<Insurer, "id" | "firm_id" | "created_at">) =>
  apiFetch<Insurer>("/insurers", { method: "POST", body: JSON.stringify(data) });

export const updateInsurer = (id: number, data: Partial<Omit<Insurer, "id" | "firm_id" | "created_at">>) =>
  apiFetch<Insurer>(`/insurers/${id}`, { method: "PUT", body: JSON.stringify(data) });

export const deleteInsurer = (id: number) =>
  apiFetch<void>(`/insurers/${id}`, { method: "DELETE" });

// ── Submissions ───────────────────────────────────────────────────────────────

export const getOrgSubmissions = (orgnr: string) =>
  apiFetch<Submission[]>(`/org/${orgnr}/submissions`);

export const createSubmission = (orgnr: string, data: Omit<Submission, "id" | "orgnr" | "insurer_name" | "created_by_email" | "created_at">) =>
  apiFetch<Submission>(`/org/${orgnr}/submissions`, { method: "POST", body: JSON.stringify(data) });

export const updateSubmission = (id: number, data: Pick<Submission, "status"> & Partial<Pick<Submission, "premium_offered_nok" | "requested_at" | "notes">>) =>
  apiFetch<Submission>(`/submissions/${id}`, { method: "PUT", body: JSON.stringify(data) });

export const deleteSubmission = (id: number) =>
  apiFetch<void>(`/submissions/${id}`, { method: "DELETE" });

// ── Client tokens ─────────────────────────────────────────────────────────────

export const getOrgClientTokens = (orgnr: string) =>
  apiFetch<ClientToken[]>(`/org/${orgnr}/client-tokens`);

export const createOrgClientToken = (orgnr: string, label?: string) =>
  apiFetch<{ token: string; orgnr: string; expires_days: number }>(
    `/org/${orgnr}/client-token${label ? `?label=${encodeURIComponent(label)}` : ""}`,
    { method: "POST" },
  );

export const getClientPortalProfile = (token: string) =>
  apiFetch<ClientPortalProfile>(`/client/${token}`);

// ── Portfolio company management ──────────────────────────────────────────────

export const addCompanyToPortfolio = (portfolioId: number, orgnr: string) =>
  apiFetch<void>(`/portfolio/${portfolioId}/companies`, {
    method: "POST",
    body: JSON.stringify({ orgnr }),
  });

// ── NL-to-SQL ─────────────────────────────────────────────────────────────────

export const nlQuery = (question: string) =>
  apiFetch<{ sql: string; columns: string[]; rows: unknown[][]; error: string | null }>(
    "/financials/query",
    { method: "POST", body: JSON.stringify({ question }) },
  );

// ── Deal pipeline (plan §🟢 #9) ──────────────────────────────────────────────

export const getPipelineStages = () =>
  apiFetch<PipelineStageOut[]>("/pipeline/stages");

export const createPipelineStage = (body: PipelineStageCreate) =>
  apiFetch<PipelineStageOut>("/pipeline/stages", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updatePipelineStage = (stageId: number, body: PipelineStageUpdate) =>
  apiFetch<PipelineStageOut>(`/pipeline/stages/${stageId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deletePipelineStage = (stageId: number) =>
  apiFetch<void>(`/pipeline/stages/${stageId}`, { method: "DELETE" });

export const getDeals = (params?: { stage_id?: number; owner_user_id?: number; orgnr?: string }) => {
  const q = new URLSearchParams();
  if (params?.stage_id != null)      q.set("stage_id", String(params.stage_id));
  if (params?.owner_user_id != null) q.set("owner_user_id", String(params.owner_user_id));
  if (params?.orgnr)                 q.set("orgnr", params.orgnr);
  const qs = q.toString();
  const suffix = qs ? "?" + qs : "";
  return apiFetch<DealOut[]>(`/deals${suffix}`);
};

export const createDeal = (body: DealCreate) =>
  apiFetch<DealOut>("/deals", { method: "POST", body: JSON.stringify(body) });

export const updateDeal = (dealId: number, body: DealUpdate) =>
  apiFetch<DealOut>(`/deals/${dealId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const moveDealStage = (dealId: number, stageId: number) =>
  apiFetch<DealOut>(`/deals/${dealId}/stage`, {
    method: "PATCH",
    body: JSON.stringify({ stage_id: stageId }),
  });

export const loseDeal = (dealId: number, reason?: string) =>
  apiFetch<DealOut>(`/deals/${dealId}/lose`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? null }),
  });

export const deleteDeal = (dealId: number) =>
  apiFetch<void>(`/deals/${dealId}`, { method: "DELETE" });

// ── Notifications inbox (plan §🟢 #17) ───────────────────────────────────────

export const getNotifications = (params?: { unread_only?: boolean; limit?: number }) => {
  const q = new URLSearchParams();
  if (params?.unread_only) q.set("unread_only", "true");
  if (params?.limit != null) q.set("limit", String(params.limit));
  const qs = q.toString();
  const suffix = qs ? "?" + qs : "";
  return apiFetch<NotificationListOut>(`/notifications${suffix}`);
};

export const markNotificationRead = (notificationId: number) =>
  apiFetch<NotificationOut>(`/notifications/${notificationId}/read`, { method: "PATCH" });

export const markAllNotificationsRead = () =>
  apiFetch<NotificationMarkReadOut>("/notifications/read-all", { method: "POST" });

// ── Risk config ─────────────────────────────────────────────────────────────
export interface RiskBand {
  label: string;
  min: number;
  max: number;
  color: string;
}

export interface RiskConfig {
  bands: RiskBand[];
  max_score: number;
}

export const getRiskConfig = () =>
  apiFetch<RiskConfig>("/risk/config");

// ── Insurance premium benchmarks ─────────────────────────────────────────

export interface PremiumEstimate {
  label: string;
  description: string;
  bracket: string;
  bracket_label: string;
  low: number;
  mid: number;
  high: number;
  nace_adjustment: number;
}

export interface PremiumBenchmarkResponse {
  mode: string;
  revenue?: number;
  nace_section?: string;
  estimates?: Record<string, PremiumEstimate>;
  brackets?: Record<string, unknown>;
  products?: Record<string, unknown>;
}

export const getInsuranceBenchmarks = (revenue?: number, naceSection?: string) => {
  const params = new URLSearchParams();
  if (revenue != null) params.set("revenue", String(revenue));
  if (naceSection) params.set("nace_section", naceSection);
  const qs = params.toString();
  const suffix = qs ? `?${qs}` : "";
  return apiFetch<PremiumBenchmarkResponse>(`/insurance/benchmarks${suffix}`);
};

// ── Coverage Analysis ────────────────────────────────────────────────────────

export interface CoverageAnalysis {
  id: number;
  orgnr: string;
  title: string;
  insurer?: string;
  product_type?: string;
  filename?: string;
  coverage_data?: Record<string, unknown>;
  premium_nok?: number;
  deductible_nok?: number;
  coverage_sum_nok?: number;
  status: string;
  created_at: string;
}

export const getOrgCoverageAnalyses = (orgnr: string) =>
  apiFetch<CoverageAnalysis[]>(`/org/${orgnr}/coverage`);

export const getCoverageAnalysis = (id: number) =>
  apiFetch<CoverageAnalysis>(`/coverage/${id}`);

export async function uploadCoverageAnalysis(
  orgnr: string,
  file: File,
  opts?: { title?: string; insurer?: string; product_type?: string }
): Promise<CoverageAnalysis> {
  const fd = new FormData();
  fd.append("file", file);
  if (opts?.title) fd.append("title", opts.title);
  if (opts?.insurer) fd.append("insurer", opts.insurer);
  if (opts?.product_type) fd.append("product_type", opts.product_type);
  const res = await fetch(`${apiBaseUrl()}/org/${orgnr}/coverage/analyse`, {
    method: "POST",
    body: fd,
    headers: _authToken ? { Authorization: `Bearer ${_authToken}` } : {},
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export const deleteCoverageAnalysis = (id: number) =>
  apiFetch<void>(`/coverage/${id}`, { method: "DELETE" });

// ── Tenders (Anbud) ──────────────────────────────────────────────────────────

export interface TenderRecipient {
  id: number;
  tender_id: number;
  insurer_name: string;
  insurer_email?: string;
  status: string;
  sent_at?: string;
  response_at?: string;
}

export interface TenderOffer {
  id: number;
  tender_id: number;
  recipient_id?: number;
  insurer_name: string;
  filename: string;
  extracted_data?: Record<string, unknown>;
  uploaded_at: string;
}

export interface Tender {
  id: number;
  orgnr: string;
  title: string;
  product_types: string[];
  deadline?: string;
  notes?: string;
  status: string;
  analysis_result?: Record<string, unknown>;
  recipients: TenderRecipient[];
  offers: TenderOffer[];
  created_by_email?: string;
  created_at: string;
}

export interface TenderListItem {
  id: number;
  orgnr: string;
  title: string;
  product_types: string[];
  deadline?: string;
  status: string;
  recipient_count: number;
  offer_count: number;
  created_at: string;
}

export const getTenders = (orgnr?: string) => {
  const qs = orgnr ? `?orgnr=${orgnr}` : "";
  return apiFetch<TenderListItem[]>(`/tenders${qs}`);
};

export const getTender = (id: number) =>
  apiFetch<Tender>(`/tenders/${id}`);

export const createTender = (data: {
  orgnr: string;
  title: string;
  product_types: string[];
  deadline?: string;
  notes?: string;
  recipients?: { insurer_name: string; insurer_email?: string }[];
}) => apiFetch<Tender>("/tenders", { method: "POST", body: JSON.stringify(data) });

export const updateTender = (id: number, data: Record<string, unknown>) =>
  apiFetch<Tender>(`/tenders/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteTender = (id: number) =>
  apiFetch<void>(`/tenders/${id}`, { method: "DELETE" });

export const sendTender = (id: number) =>
  apiFetch<Tender>(`/tenders/${id}/send`, { method: "POST" });

export const remindTender = (id: number) =>
  apiFetch<{ reminders_sent: number; reminders_failed: number }>(
    `/tenders/${id}/remind`,
    { method: "POST" },
  );

export async function downloadTenderPresentationPdf(
  id: number,
  filename: string,
): Promise<void> {
  await downloadFile(`/bapi/tenders/${id}/presentation/pdf`, filename);
}

export async function uploadTenderOffer(
  tenderId: number,
  file: File,
  insurerName: string,
  recipientId?: number
): Promise<TenderOffer> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("insurer_name", insurerName);
  if (recipientId) fd.append("recipient_id", String(recipientId));
  const res = await fetch(`${apiBaseUrl()}/tenders/${tenderId}/offers`, {
    method: "POST",
    body: fd,
    headers: _authToken ? { Authorization: `Bearer ${_authToken}` } : {},
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export const analyseTender = (id: number) =>
  apiFetch<{ tender_id: number; analysis: Record<string, unknown> }>(
    `/tenders/${id}/analyse`,
    { method: "POST" }
  );
