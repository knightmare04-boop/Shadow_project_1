// Mirrors app/schemas/*.py — kept hand-in-sync deliberately (no codegen step
// yet; see Module 6 follow-up to generate these from /openapi.json).

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  correlation_id: string;
  errors?: Array<{ loc: (string | number)[]; msg: string; type: string }>;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
  full_name: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  role: "erp_clerk" | "forensic_auditor" | "system_administrator";
}

export interface Vendor {
  id: string;
  vendor_code: string;
  legal_name: string;
  tax_id: string | null;
  is_active: boolean;
  is_blocked: boolean;
  created_at: string;
}

export interface InvoiceLine {
  id?: string;
  line_no: number;
  po_line_id?: string | null;
  description: string;
  quantity: number;
  unit_price: string;
  gl_account_id: string;
  line_total?: string;
}

export interface Invoice {
  id: string;
  invoice_number: string;
  vendor_id: string;
  total_amount: string;
  status: string;
  match_status: string;
  duplicate_check_status: string;
  invoice_date: string;
  created_at: string;
  lines: InvoiceLine[];
}

export interface Payment {
  id: string;
  invoice_id: string;
  vendor_id: string;
  amount: string;
  status: string;
  payment_date: string | null;
  failure_reason: string | null;
  created_at: string;
}

export interface RiskDriver {
  feature: string;
  value: number | null;
  shap: number;
  family: string;
}

export interface Alert {
  id: string;
  dataset: string;
  transaction_id: string;
  payment_id: string | null;
  score: number;
  threshold: number;
  risk_drivers: RiskDriver[];
  graph_evidence: Record<string, unknown>;
  model_artifact: string;
  feedback_status: string;
  feedback_note: string | null;
  created_at: string;
}
