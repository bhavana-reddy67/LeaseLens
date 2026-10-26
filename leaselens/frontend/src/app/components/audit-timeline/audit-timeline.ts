import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { AuditEvent } from '../../models';

const STAGE_LABELS: Record<string, string> = {
  input: 'Input check',
  segmentation: 'Clause splitting',
  safety_check: 'Prompt-injection check',
  rule_screening: 'Keyword rules',
  ai_analysis: 'AI analysis',
  retrieval: 'Guidance retrieval',
  risk_assessment: 'Risk assessment',
  review: 'Ready for your review',
};

const STATUS_BADGES: Record<AuditEvent['status'], string> = {
  completed: 'badge badge--low',
  warning: 'badge badge--medium',
  retried: 'badge badge--medium',
  failed: 'badge badge--high',
  skipped: 'badge badge--neutral',
};

@Component({
  selector: 'app-audit-timeline',
  imports: [DatePipe],
  templateUrl: './audit-timeline.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuditTimeline {
  readonly events = input.required<AuditEvent[]>();

  stageLabel(stage: string): string {
    return STAGE_LABELS[stage] ?? stage;
  }

  badgeClass(status: AuditEvent['status']): string {
    return STATUS_BADGES[status];
  }
}
