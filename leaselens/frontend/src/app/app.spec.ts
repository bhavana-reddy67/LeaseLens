import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { App } from './app';
import { ExtractionResponse, ProvidersResponse } from './models';

const PROVIDERS: ProvidersResponse = {
  default_provider: 'ollama',
  max_upload_mb: 10,
  ocr_available: false,
  providers: [
    {
      name: 'ollama', label: 'Local Ollama', model: 'gemma4', local: true, configured: true,
      available: true, capabilities: ['completion', 'vision'], detail: 'Ready.',
    },
    {
      name: 'google', label: 'Google Gemini API', model: 'gemma-4-26b-a4b-it', local: false,
      configured: false, available: false, capabilities: [], detail: 'Optional. Set GOOGLE_API_KEY.',
    },
  ],
};

const EXTRACTION: ExtractionResponse = {
  file_name: 'lease.pdf', file_type: 'pdf', page_count: 1, total_chars: 60,
  pages: [{ page: 1, text: 'This lease shall automatically renew unless notice is given.', method: 'pdf_text' }],
  methods_used: ['pdf_text'], warnings: [], retention_note: 'The uploaded file was deleted.',
};

describe('App', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('renders the dashboard and the local privacy notice', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    http.expectOne('/api/providers').flush(PROVIDERS);
    await fixture.whenStable();
    fixture.detectChanges();

    const page = fixture.nativeElement as HTMLElement;
    expect(page.querySelector('h1')?.textContent).toContain('Spot risky clauses');
    expect(page.textContent).toContain('processed on this computer');
    expect(page.textContent).toContain('gemma-4-26b-a4b-it');
    expect(page.textContent).toContain('Not configured');
  });

  it('shows a readable message when the backend is down', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    http.expectOne('/api/providers').error(new ProgressEvent('error'), { status: 0 });
    await fixture.whenStable();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Cannot reach the LeaseLens server');
  });

  it('sends the reviewed text to the selected local provider', async () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne('/api/providers').flush(PROVIDERS);

    app.extract(new File(['%PDF-'], 'lease.pdf', { type: 'application/pdf' }));
    http.expectOne('/api/documents/extract').flush(EXTRACTION);
    app.onPageEdited({ page: 1, text: 'Edited clause text that automatically renews.' });
    expect(app.canAnalyze()).toBe(true);

    app.analyze();
    const request = http.expectOne('/api/analyze');
    expect(request.request.body).toEqual({
      category: 'rental',
      pages: [{ page: 1, text: 'Edited clause text that automatically renews.' }],
      provider: 'ollama',
      allow_cloud_processing: false,
    });
    request.flush({}, { status: 503, statusText: 'Unavailable' });
    expect(app.analyzeError()).toContain('HTTP 503');
    expect(app.analyzing()).toBe(false);
  });

  it('blocks analysis with an unavailable cloud provider and no consent', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne('/api/providers').flush(PROVIDERS);
    app.pages.set(EXTRACTION.pages);
    app.provider.set('google');
    expect(app.canAnalyze()).toBe(false);
    expect(app.analyzeBlockedReason()).toContain('not available');
  });
});
