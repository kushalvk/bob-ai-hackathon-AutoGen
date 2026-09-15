/**
 * Core clinical compliance domain models and API response types.
 */

export interface ContributingFactor {
  factor: string;
  name: string;
  weight: number;
  raw_value: number;
  normalized_score: number;
  contribution: number;
}

export interface SiteRiskScore {
  score_id: string;
  site_id: string;
  score: number;
  computed_at: string;
  contributing_factors: ContributingFactor[];
  // Decorated frontend fields
  name?: string;
  country?: string;
  enrollment_target?: number;
  enrolled_patients?: number;
  staff_turnover_rate?: number;
  deviation_count?: number;
  major_deviation_count?: number;
  trend?: 'up' | 'down' | 'stable';
}

export interface DeviationEvidence {
  field?: string;
  expected?: any;
  actual?: any;
  delta?: any;
  [key: string]: any;
}

export interface Deviation {
  deviation_id: string;
  record_id?: string | null;
  site_id: string;
  type: string;
  severity: 'major' | 'minor' | 'administrative' | string;
  default_severity?: 'major' | 'minor' | 'administrative' | string;
  final_severity?: 'major' | 'minor' | 'administrative' | string;
  severity_rationale: string;
  severity_source?: 'deterministic' | 'llm_override' | string;
  evidence: DeviationEvidence;
  detected_at?: string | null;
  patient_id?: string;
  visit_name?: string;
}

export interface CAPAReport {
  capa_id: string;
  deviation_ids: string[];
  finding?: string;
  severity?: string;
  severity_rationale?: string;
  root_cause: string;
  corrective_action: string;
  preventive_action: string;
  owner: string;
  due_date: string;
  status: 'open' | 'in_progress' | 'pending_review' | 'closed' | string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  tool_called?: string;
  tool_arguments?: Record<string, any>;
  tool_result?: any;
  grounded?: boolean;
}
