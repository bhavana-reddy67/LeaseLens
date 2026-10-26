import { AnalyzeResponse, Finding } from './models';
import { formatBytes, formatEmail, formatReport } from './report-format';

const FINDING: Finding = {
  id: 'p1-c1:auto_renewal',
  clause_id: 'p1-c1',
  category: 'auto_renewal',
  category_label: 'Automatic renewal',
  excerpt: 'This lease shall automatically renew.',
  page: 1,
  risk_level: 'high',
  reason: 'Long notice window.',
  impact: 'Locked in for another year.',
  questions: ['When is the last day to cancel?'],
  references: [{ source_id: 'KB-AR-01', title: 'Automatic renewal', kind: 'general_guidance', relevance: 'x', score: 0.5 }],
  rule_hits: [],
  rule_level: 'high',
  ai_level: 'high',
  assessed_by: ['rules', 'ai'],
  evidence_agreement: 'high',
  uncertainty_notes: [],
};

const RESULT: AnalyzeResponse = {
  provider: 'ollama',
  model: 'gemma4',
  processed_locally: true,
  category: 'rental',
  ai_status: 'completed',
  summary: { overall: 'high', counts: { high: 1, medium: 0, low: 0, uncertain: 0 }, headline: '1 finding(s).' },
  findings: [FINDING],
  warnings: [],
  audit: [],
  disclaimer: 'LeaseLens is an informational tool, not a lawyer.',
};

describe('formatReport', () => {
  it('includes the finding, page, questions, sources and disclaimer', () => {
    const text = formatReport(RESULT, [FINDING], 'lease.pdf');
    expect(text).toContain('lease.pdf (Rental agreement)');
    expect(text).toContain('[High] Automatic renewal (page 1)');
    expect(text).toContain('When is the last day to cancel?');
    expect(text).toContain('KB-AR-01');
    expect(text).toContain('(processed locally)');
    expect(text.trim().endsWith('not a lawyer.')).toBe(true);
  });
});

describe('formatting helpers', () => {
  it('formats email and sizes', () => {
    expect(formatEmail('Hi', 'Body')).toBe('Subject: Hi\n\nBody');
    expect(formatBytes(500)).toBe('500 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(3 * 1024 * 1024)).toBe('3.0 MB');
  });
});
