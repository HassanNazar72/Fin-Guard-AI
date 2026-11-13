// Mirrors the FastAPI response contracts in backend/main.py and backend/schemas.py.

export type Mode = "live" | "cached" | "fallback" | "blocked";

export type TransactionFlag =
  | "pii_redacted"
  | "injection_blocked"
  | "duplicate"
  | "outlier"
  | "price_increase";

export interface SecurityEvent {
  type: "pii_redacted" | "injection_blocked" | "prompt_rejected" | "rate_limited";
  detail: string;
  txn_id: string | null;
  field: string | null;
}

export interface SecuritySummary {
  pii_fields_scrubbed: number;
  injections_blocked: number;
  prompt_blocked?: boolean;
  events: SecurityEvent[];
}

export interface Quota {
  remaining: number;
  limit: number;
}

export interface Transaction {
  txn_id: string;
  date: string;
  time: string;
  merchant: string;
  amount: number;
  currency: string;
  category: string;
  flags: TransactionFlag[];
}

export interface RecurringMerchant {
  merchant: string;
  category: string;
  charges: number;
  previous_amount: number;
  latest_amount: number;
  price_change_pct: number;
  flagged_increase: boolean;
  annualised_increase: number;
}

export interface DuplicateCharge {
  merchant: string;
  amount: number;
  first_txn_id: string;
  second_txn_id: string;
  first_at: string;
  second_at: string;
  hours_apart: number;
}

export interface OutlierCharge {
  txn_id: string;
  date: string;
  merchant: string;
  category: string;
  amount: number;
  z_score: number;
}

export interface MonthlyCategoryRow {
  month: string;
  [category: string]: string | number;
}

export interface DailyPoint {
  date: string;
  spend: number;
  cumulative: number;
}

export interface AnalyzeResponse {
  source: "sample" | "upload";
  summary: {
    rows_in: number;
    rows_analyzed: number;
    duplicates_dropped: number;
    invalid_rows_dropped: number;
    warnings: string[];
    period_start: string;
    period_end: string;
    currency: string;
  };
  kpis: {
    total_income: number;
    total_spend: number;
    net_cashflow: number;
    savings_rate_pct: number | null;
    anomalies_detected: number;
    duplicates: number;
    outliers: number;
    subscription_increases: number;
  };
  charts: {
    monthly_category: { categories: string[]; rows: MonthlyCategoryRow[] };
    daily_cumulative: DailyPoint[];
  };
  insights: {
    subscriptions: {
      recurring_merchants: RecurringMerchant[];
      flagged_increases: RecurringMerchant[];
      total_monthly_recurring: number;
    };
    anomalies: {
      duplicates: DuplicateCharge[];
      outliers: OutlierCharge[];
      mean_spend: number;
      outlier_threshold: number;
    };
  };
  transactions: Transaction[];
  security: SecuritySummary;
  quota: Quota;
  live_ai_enabled: boolean;
  model: string;
}

export interface FinancialInsightReport {
  answer: string;
  tools_invoked: string[];
  flagged_risks: string[];
  confidence_score: number;
  requires_human_review: boolean;
}

export interface ExecutionTrace {
  model: string;
  mode: Mode;
  tools_called: string[];
  tool_timings: { name: string; duration_ms: number }[];
  confidence_score: number;
  schema_validated: boolean;
  latency_ms: number;
  llm_calls: number;
  input_tokens: number | null;
  output_tokens: number | null;
}

export interface ChatResponse {
  report: FinancialInsightReport;
  trace: ExecutionTrace;
  status: { mode: Mode; message: string | null };
  quota: Quota;
  security: SecuritySummary;
}
