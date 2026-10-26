import { TestBed } from '@angular/core/testing';

import { AnalyzeResponse, Finding } from '../../models';
import { Results } from './results';

function finding(id: string, risk: Finding['risk_level'], category: string, label: string): Finding {
  return {
    id, clause_id: id, category, category_label: label, excerpt: `Excerpt ${id}`, page: 1,
    risk_level: risk, reason: 'reason', impact: 'impact', questions: [], references: [], rule_hits: [],
    rule_level: null, ai_level: risk, assessed_by: ['ai'], evidence_agreement: 'medium',
    uncertainty_notes: [],
  };
}

const RESULT: AnalyzeResponse = {
  provider: 'ollama', model: 'gemma4', processed_locally: true, category: 'rental', ai_status: 'completed',
  summary: { overall: 'high', counts: { high: 1, medium: 1, low: 1, uncertain: 0 }, headline: '3 finding(s).' },
  findings: [
    finding('a', 'high', 'fees', 'Hidden or additional fees'),
    finding('b', 'medium', 'auto_renewal', 'Automatic renewal'),
    finding('c', 'low', 'fees', 'Hidden or additional fees'),
  ],
  warnings: [], audit: [], disclaimer: 'Not legal advice.',
};

describe('Results', () => {
  async function create() {
    await TestBed.configureTestingModule({ imports: [Results] }).compileComponents();
    const fixture = TestBed.createComponent(Results);
    fixture.componentRef.setInput('result', RESULT);
    fixture.detectChanges();
    return fixture;
  }

  it('filters by risk level and category', async () => {
    const fixture = await create();
    const results = fixture.componentInstance;
    expect(results.filtered().length).toBe(3);

    results.riskFilter.set('high');
    expect(results.filtered().map((f) => f.id)).toEqual(['a']);

    results.riskFilter.set('all');
    results.categoryFilter.set('fees');
    expect(results.filtered().map((f) => f.id)).toEqual(['a', 'c']);
    expect(results.categories().map((c) => c.id)).toEqual(['auto_renewal', 'fees']);
  });

  it('tracks findings selected for the email', async () => {
    const fixture = await create();
    const results = fixture.componentInstance;
    results.toggle('b', { target: { checked: true } } as unknown as Event);
    results.toggle('a', { target: { checked: true } } as unknown as Event);
    results.toggle('b', { target: { checked: false } } as unknown as Event);
    expect(results.selectedIds()).toEqual(['a']);
  });

  it('renders counts and excerpts', async () => {
    const fixture = await create();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Excerpt a');
    expect(text).toContain('Highest: High');
    expect(text).toContain('Not legal advice.');
  });
});
