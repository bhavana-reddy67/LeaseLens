/** Types that mirror the FastAPI response schemas (backend/app/schemas). */

export type ProviderName = 'ollama' | 'google';
export type DocumentCategory = 'rental' | 'employment' | 'loan' | 'other';
export type RiskLevel = 'high' | 'medium' | 'low' | 'uncertain';
export type EvidenceAgreement = 'high' | 'medium' | 'low';
export type ExtractionMethod = 'pdf_text' | 'ocr' | 'vision_model' | 'none';

export const DOCUMENT_CATEGORIES: { value: DocumentCategory; label: string }[] = [
  { value: 'rental', label: 'Rental agreement' },
  { value: 'employment', label: 'Employment contract' },
  { value: 'loan', label: 'Loan agreement' },
  { value: 'other', label: 'Other contract' },
];

export const RISK_LEVELS: RiskLevel[] = ['high', 'medium', 'low', 'uncertain'];

export const RISK_LABELS: Record<RiskLevel, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  uncertain: 'Uncertain',
};

export const EXTRACTION_METHOD_LABELS: Record<ExtractionMethod, string> = {
  pdf_text: 'PDF text',
  ocr: 'OCR (Tesseract)',
  vision_model: 'Local Gemma vision',
  none: 'No text found',
};

export interface ProviderStatus {
  name: ProviderName;
  label: string;
  model: string;
  local: boolean;
  configured: boolean;
  available: boolean;
  capabilities: string[];
  detail: string;
}

export interface ProvidersResponse {
  default_provider: ProviderName;
  providers: ProviderStatus[];
  max_upload_mb: number;
  ocr_available: boolean;
}

export interface PageText {
  page: number;
  text: string;
  method: ExtractionMethod;
}

export interface ExtractionResponse {
  file_name: string;
  file_type: 'pdf' | 'jpeg' | 'png';
  page_count: number;
  pages: PageText[];
  total_chars: number;
  methods_used: ExtractionMethod[];
  warnings: string[];
  retention_note: string;
}

export interface KnowledgeReference {
  source_id: string;
  title: string;
  kind: 'general_guidance';
  relevance: string;
  score: number;
}

export interface RuleHit {
  rule_id: string;
  description: string;
  level: 'high' | 'medium' | 'low';
}

export interface Finding {
  id: string;
  clause_id: string;
  category: string;
  category_label: string;
  excerpt: string;
  page: number | null;
  risk_level: RiskLevel;
  reason: string;
  impact: string;
  questions: string[];
  references: KnowledgeReference[];
  rule_hits: RuleHit[];
  rule_level: 'high' | 'medium' | 'low' | null;
  ai_level: RiskLevel | null;
  assessed_by: ('rules' | 'ai')[];
  evidence_agreement: EvidenceAgreement;
  uncertainty_notes: string[];
}

export interface RiskSummary {
  overall: RiskLevel | null;
  counts: Record<RiskLevel, number>;
  headline: string;
}

export interface AuditEvent {
  stage: string;
  status: 'completed' | 'warning' | 'failed' | 'retried' | 'skipped';
  detail: string;
  sources: string[];
  timestamp: string;
}

export interface AnalyzeRequest {
  category: DocumentCategory;
  pages: { page: number; text: string }[];
  provider: ProviderName;
  allow_cloud_processing: boolean;
}

export interface AnalyzeResponse {
  provider: ProviderName;
  model: string;
  processed_locally: boolean;
  category: DocumentCategory;
  ai_status: 'completed' | 'partial' | 'failed';
  summary: RiskSummary;
  findings: Finding[];
  warnings: string[];
  audit: AuditEvent[];
  disclaimer: string;
}

export type EmailTone = 'polite' | 'formal' | 'friendly';

export interface NegotiationEmailRequest {
  document_category: DocumentCategory;
  findings: {
    category_label: string;
    excerpt: string;
    reason: string;
    questions: string[];
    page: number | null;
  }[];
  recipient_role: string;
  recipient_name: string;
  sender_name: string;
  tone: EmailTone;
  provider: ProviderName;
  allow_cloud_processing: boolean;
}

export interface NegotiationEmailResponse {
  subject: string;
  body: string;
  provider: ProviderName;
  model: string;
  warnings: string[];
}
