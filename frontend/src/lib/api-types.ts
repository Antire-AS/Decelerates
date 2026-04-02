// ── Shared TypeScript types for the API client ────────────────────────────────
// All types are exported here and re-exported from api.ts so that
// existing `import { SomeType } from "@/lib/api"` imports continue to work.

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
  omsetning?: number;
  sum_egenkapital?: number;
  egenkapitalandel?: number;
  regnskapsår?: number;
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
  start_date?: string;
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

export interface PortfolioItem {
  id: number;
  name: string;
  description?: string;
  created_at: string;
}

export interface BrokerNote {
  id: number;
  text: string;
  created_at: string;
}

export interface CommissionAnalytics {
  total_commission_nok: number;
  policy_count: number;
  by_product: {
    product_type: string;
    count: number;
    commission: number;
    premium: number;
    avg_rate_pct: number;
    share_pct: number;
  }[];
  by_insurer: {
    insurer: string;
    count: number;
    commission: number;
    premium: number;
    avg_rate_pct: number;
    share_pct: number;
  }[];
}

export interface IddBehovsanalyse {
  id: number;
  orgnr: string;
  created_by_email?: string;
  created_at: string;
  client_name?: string;
  client_contact_name?: string;
  client_contact_email?: string;
  existing_insurance?: { insurer: string; product: string; premium?: number }[];
  risk_appetite?: string;
  property_owned: boolean;
  has_employees: boolean;
  has_vehicles: boolean;
  has_professional_liability: boolean;
  has_cyber_risk: boolean;
  annual_revenue_nok?: number;
  special_requirements?: string;
  recommended_products?: string[];
  advisor_notes?: string;
  suitability_basis?: string;
  fee_basis?: string;
  fee_amount_nok?: number;
}

export interface ClientToken {
  token: string;
  label?: string;
  expires_at: string;
  created_at: string;
}

export interface ClientPortalProfile {
  orgnr: string;
  navn?: string;
  kommune?: string;
  naeringskode1_beskrivelse?: string;
  antall_ansatte?: number;
  risk_score?: number;
  risk_reasons?: string[];
  expires_at: string;
  policies: {
    insurer: string;
    product_type: string;
    policy_number?: string;
    annual_premium_nok?: number;
    renewal_date?: string;
  }[];
  claims: {
    claim_number?: string;
    status: string;
    incident_date?: string;
    description?: string;
  }[];
  documents: {
    title: string;
    uploaded_at?: string;
  }[];
}
