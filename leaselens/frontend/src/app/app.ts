import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { Subscription } from 'rxjs';

import { ApiService, toApiError } from './api.service';
import { copyToClipboard } from './clipboard';
import { AuditTimeline } from './components/audit-timeline/audit-timeline';
import { EmailComposer } from './components/email-composer/email-composer';
import { ProviderPanel } from './components/provider-panel/provider-panel';
import { Results } from './components/results/results';
import { TextReview } from './components/text-review/text-review';
import { UploadPanel } from './components/upload-panel/upload-panel';
import {
  AnalyzeResponse,
  DOCUMENT_CATEGORIES,
  DocumentCategory,
  ExtractionResponse,
  Finding,
  PageText,
  ProviderName,
  ProvidersResponse,
} from './models';
import { formatReport } from './report-format';

@Component({
  selector: 'app-root',
  imports: [ProviderPanel, UploadPanel, TextReview, Results, AuditTimeline, EmailComposer],
  templateUrl: './app.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App implements OnInit {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);

  // Step 1: provider
  readonly providers = signal<ProvidersResponse | null>(null);
  readonly providersLoading = signal(false);
  readonly providersError = signal<string | null>(null);
  readonly provider = signal<ProviderName>('ollama');
  readonly cloudConsent = signal(false);

  // Step 2: upload + extraction
  readonly category = signal<DocumentCategory>('rental');
  readonly file = signal<File | null>(null);
  readonly extraction = signal<ExtractionResponse | null>(null);
  readonly pages = signal<PageText[]>([]);
  readonly extracting = signal(false);
  readonly extractError = signal<string | null>(null);

  // Steps 3-5: analysis and email
  readonly analysis = signal<AnalyzeResponse | null>(null);
  readonly analyzing = signal(false);
  readonly analyzeError = signal<string | null>(null);
  readonly elapsedSeconds = signal(0);
  readonly selectedFindingIds = signal<string[]>([]);
  readonly reportCopyMessage = signal<string | null>(null);

  private activeRequest?: Subscription;
  private timer?: ReturnType<typeof setInterval>;

  readonly maxUploadMb = computed(() => this.providers()?.max_upload_mb ?? 10);
  readonly selectedProvider = computed(
    () => this.providers()?.providers.find((p) => p.name === this.provider()) ?? null,
  );
  readonly providerReady = computed(() => {
    const status = this.selectedProvider();
    return !!status && status.available && (status.local || this.cloudConsent());
  });
  readonly hasText = computed(() => this.pages().some((p) => p.text.trim().length > 0));
  readonly canAnalyze = computed(() => this.hasText() && this.providerReady() && !this.analyzing());
  readonly categoryLabel = computed(
    () => DOCUMENT_CATEGORIES.find((c) => c.value === this.category())?.label ?? 'Contract',
  );
  readonly selectedFindings = computed<Finding[]>(() => {
    const ids = new Set(this.selectedFindingIds());
    return this.analysis()?.findings.filter((f) => ids.has(f.id)) ?? [];
  });
  readonly analyzeBlockedReason = computed(() => {
    const status = this.selectedProvider();
    if (!this.hasText()) {
      return 'There is no text to analyse.';
    }
    if (!status) {
      return 'Provider status is not loaded yet. Use "Refresh status" in step 1.';
    }
    if (!status.available) {
      return `${status.label} is not available: ${status.detail}`;
    }
    if (!status.local && !this.cloudConsent()) {
      return 'Confirm cloud processing in step 1 to use the Google API.';
    }
    return null;
  });

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.activeRequest?.unsubscribe();
      this.stopTimer();
    });
  }

  ngOnInit(): void {
    this.loadProviders(true);
  }

  loadProviders(useServerDefault = false): void {
    this.providersLoading.set(true);
    this.providersError.set(null);
    this.api.getProviders().subscribe({
      next: (info) => {
        this.providers.set(info);
        if (useServerDefault) {
          this.provider.set(info.default_provider);
        }
        this.providersLoading.set(false);
      },
      error: (err: unknown) => {
        this.providersError.set(toApiError(err).message);
        this.providersLoading.set(false);
      },
    });
  }

  onFileCleared(): void {
    this.activeRequest?.unsubscribe();
    this.extracting.set(false);
    this.analyzing.set(false);
    this.stopTimer();
    this.clearDocumentData();
  }

  extract(file: File): void {
    this.activeRequest?.unsubscribe();
    this.clearDocumentData();
    this.extracting.set(true);
    this.activeRequest = this.api.extract(file).subscribe({
      next: (result) => {
        this.extraction.set(result);
        this.pages.set(result.pages.map((p) => ({ ...p })));
        this.extracting.set(false);
      },
      error: (err: unknown) => {
        this.extractError.set(toApiError(err).message);
        this.extracting.set(false);
      },
    });
  }

  onPageEdited(edit: { page: number; text: string }): void {
    this.pages.update((pages) => pages.map((p) => (p.page === edit.page ? { ...p, text: edit.text } : p)));
    this.analysis.set(null); // earlier results no longer match the text
    this.selectedFindingIds.set([]);
  }

  resetEdits(): void {
    const original = this.extraction();
    if (original) {
      this.pages.set(original.pages.map((p) => ({ ...p })));
      this.analysis.set(null);
      this.selectedFindingIds.set([]);
    }
  }

  analyze(): void {
    if (!this.canAnalyze()) {
      return;
    }
    this.activeRequest?.unsubscribe();
    this.analysis.set(null);
    this.analyzeError.set(null);
    this.selectedFindingIds.set([]);
    this.reportCopyMessage.set(null);
    this.analyzing.set(true);
    this.startTimer();

    this.activeRequest = this.api
      .analyze({
        category: this.category(),
        pages: this.pages().map((p) => ({ page: p.page, text: p.text })),
        provider: this.provider(),
        allow_cloud_processing: this.provider() === 'google' && this.cloudConsent(),
      })
      .subscribe({
        next: (result) => {
          this.analysis.set(result);
          this.analyzing.set(false);
          this.stopTimer();
          setTimeout(() => document.getElementById('results-heading')?.focus());
        },
        error: (err: unknown) => {
          this.analyzeError.set(toApiError(err).message);
          this.analyzing.set(false);
          this.stopTimer();
        },
      });
  }

  cancelAnalysis(): void {
    this.activeRequest?.unsubscribe();
    this.analyzing.set(false);
    this.stopTimer();
    this.analyzeError.set('Analysis cancelled. The server may finish its current step before stopping.');
  }

  async copyReport(findings: Finding[]): Promise<void> {
    const result = this.analysis();
    if (!result) {
      return;
    }
    const ok = await copyToClipboard(formatReport(result, findings, this.extraction()?.file_name ?? null));
    this.reportCopyMessage.set(
      ok ? `Report with ${findings.length} finding(s) copied to the clipboard.` : 'Copy failed. Please try again.',
    );
  }

  startOver(): void {
    this.file.set(null);
    this.onFileCleared();
    window.scrollTo({ top: 0 });
  }

  private clearDocumentData(): void {
    this.extraction.set(null);
    this.pages.set([]);
    this.extractError.set(null);
    this.analysis.set(null);
    this.analyzeError.set(null);
    this.selectedFindingIds.set([]);
    this.reportCopyMessage.set(null);
  }

  private startTimer(): void {
    this.stopTimer();
    const started = Date.now();
    this.elapsedSeconds.set(0);
    this.timer = setInterval(() => this.elapsedSeconds.set(Math.round((Date.now() - started) / 1000)), 1000);
  }

  private stopTimer(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
  }
}
