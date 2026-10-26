import { ChangeDetectionStrategy, Component, computed, input, model, output, signal } from '@angular/core';

import { AnalyzeResponse, Finding, RISK_LABELS, RISK_LEVELS, RiskLevel } from '../../models';

const AGREEMENT_LABELS = {
  high: 'Rules and AI agree',
  medium: 'Partly supported',
  low: 'Weak or single source',
} as const;

@Component({
  selector: 'app-results',
  templateUrl: './results.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Results {
  readonly result = input.required<AnalyzeResponse>();
  readonly selectedIds = model<string[]>([]);
  readonly copyReport = output<Finding[]>();
  readonly copyMessage = input<string | null>(null);

  readonly riskLevels = RISK_LEVELS;
  readonly riskLabels = RISK_LABELS;
  readonly agreementLabels = AGREEMENT_LABELS;

  readonly riskFilter = signal<RiskLevel | 'all'>('all');
  readonly categoryFilter = signal<string>('all');

  readonly categories = computed(() => {
    const seen = new Map<string, string>();
    for (const finding of this.result().findings) {
      seen.set(finding.category, finding.category_label);
    }
    return [...seen.entries()].map(([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label));
  });

  readonly filtered = computed(() =>
    this.result().findings.filter(
      (f) =>
        (this.riskFilter() === 'all' || f.risk_level === this.riskFilter()) &&
        (this.categoryFilter() === 'all' || f.category === this.categoryFilter()),
    ),
  );

  isSelected(id: string): boolean {
    return this.selectedIds().includes(id);
  }

  toggle(id: string, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    const current = this.selectedIds().filter((x) => x !== id);
    this.selectedIds.set(checked ? [...current, id] : current);
  }

  onRiskFilter(event: Event): void {
    this.riskFilter.set((event.target as HTMLSelectElement).value as RiskLevel | 'all');
  }

  onCategoryFilter(event: Event): void {
    this.categoryFilter.set((event.target as HTMLSelectElement).value);
  }

  clearFilters(): void {
    this.riskFilter.set('all');
    this.categoryFilter.set('all');
  }

  assessedByText(finding: Finding): string {
    const parts = finding.assessed_by.map((source) => (source === 'ai' ? 'AI model' : 'keyword rules'));
    return parts.join(' + ');
  }
}
