import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { Subscription } from 'rxjs';

import { ApiService, toApiError } from '../../api.service';
import { copyToClipboard } from '../../clipboard';
import { DocumentCategory, EmailTone, Finding, ProviderName, RISK_LABELS } from '../../models';
import { formatEmail } from '../../report-format';

@Component({
  selector: 'app-email-composer',
  templateUrl: './email-composer.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EmailComposer {
  private readonly api = inject(ApiService);

  readonly findings = input.required<Finding[]>();
  readonly documentCategory = input.required<DocumentCategory>();
  readonly provider = input.required<ProviderName>();
  readonly cloudConsent = input(false);
  readonly providerReady = input(true);

  readonly riskLabels = RISK_LABELS;
  readonly recipientRole = signal('');
  readonly recipientName = signal('');
  readonly senderName = signal('');
  readonly tone = signal<EmailTone>('polite');

  readonly subject = signal('');
  readonly body = signal('');
  readonly warnings = signal<string[]>([]);
  readonly generating = signal(false);
  readonly error = signal<string | null>(null);
  readonly copyMessage = signal<string | null>(null);
  readonly hasDraft = signal(false);

  private request?: Subscription;

  readonly tones: { value: EmailTone; label: string }[] = [
    { value: 'polite', label: 'Polite' },
    { value: 'formal', label: 'Formal' },
    { value: 'friendly', label: 'Friendly' },
  ];

  text(event: Event): string {
    return (event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value;
  }

  setTone(event: Event): void {
    this.tone.set(this.text(event) as EmailTone);
  }

  generate(): void {
    const selected = this.findings();
    if (!selected.length || this.generating()) {
      return;
    }
    this.generating.set(true);
    this.error.set(null);
    this.copyMessage.set(null);
    this.request?.unsubscribe();
    this.request = this.api
      .draftEmail({
        document_category: this.documentCategory(),
        findings: selected.map((f) => ({
          category_label: f.category_label,
          excerpt: f.excerpt,
          reason: f.reason,
          questions: f.questions.slice(0, 6),
          page: f.page,
        })),
        recipient_role: this.recipientRole().trim(),
        recipient_name: this.recipientName().trim(),
        sender_name: this.senderName().trim(),
        tone: this.tone(),
        provider: this.provider(),
        allow_cloud_processing: this.provider() === 'google' && this.cloudConsent(),
      })
      .subscribe({
        next: (draft) => {
          this.subject.set(draft.subject);
          this.body.set(draft.body);
          this.warnings.set(draft.warnings);
          this.hasDraft.set(true);
          this.generating.set(false);
        },
        error: (err: unknown) => {
          this.error.set(toApiError(err).message);
          this.generating.set(false);
        },
      });
  }

  async copy(): Promise<void> {
    const ok = await copyToClipboard(formatEmail(this.subject(), this.body()));
    this.copyMessage.set(ok ? 'Email copied to the clipboard.' : 'Copy failed. Select the text and copy it manually.');
  }
}
