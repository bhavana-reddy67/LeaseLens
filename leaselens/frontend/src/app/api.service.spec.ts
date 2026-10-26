import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ApiError, ApiService, toApiError } from './api.service';

describe('ApiService', () => {
  let api: ApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(ApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('uploads the file as multipart form data', () => {
    const file = new File(['%PDF-1.7'], 'lease.pdf', { type: 'application/pdf' });
    api.extract(file).subscribe();
    const request = http.expectOne('/api/documents/extract');
    expect(request.request.method).toBe('POST');
    expect(request.request.body instanceof FormData).toBe(true);
    expect((request.request.body as FormData).get('file')).toBeTruthy();
    request.flush({});
  });

  it('maps the server error message', () => {
    let error: ApiError | undefined;
    api.getProviders().subscribe({ error: (e: ApiError) => (error = e) });
    http
      .expectOne('/api/providers')
      .flush({ error: { code: 'model_not_found', message: "Run 'ollama pull gemma4'." } }, { status: 503, statusText: 'x' });
    expect(error?.message).toBe("Run 'ollama pull gemma4'.");
    expect(error?.code).toBe('model_not_found');
    expect(error?.status).toBe(503);
  });
});

describe('toApiError', () => {
  it('explains network failures', () => {
    const error = toApiError(new HttpErrorResponse({ status: 0 }));
    expect(error.code).toBe('network_error');
    expect(error.message).toContain('backend is running');
  });

  it('never exposes raw error bodies', () => {
    const error = toApiError(new HttpErrorResponse({ status: 500, error: 'Traceback (most recent call last) ...' }));
    expect(error.message).not.toContain('Traceback');
  });
});
