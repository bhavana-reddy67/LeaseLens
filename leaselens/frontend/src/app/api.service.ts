import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, throwError } from 'rxjs';

import {
  AnalyzeRequest,
  AnalyzeResponse,
  ExtractionResponse,
  NegotiationEmailRequest,
  NegotiationEmailResponse,
  ProvidersResponse,
} from './models';

/** The dev server proxies /api to the FastAPI backend (see proxy.conf.json). */
export const API_BASE = '/api';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string };
}

/** Turn any HTTP failure into a short, readable message. Never shows stack traces. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  if (error instanceof HttpErrorResponse) {
    if (error.status === 0) {
      return new ApiError(
        'Cannot reach the LeaseLens server. Make sure the backend is running on port 8000.',
        0,
        'network_error',
      );
    }
    const body = error.error as ErrorBody | null;
    const message = body?.error?.message;
    if (typeof message === 'string' && message.length > 0) {
      return new ApiError(message, error.status, body?.error?.code ?? 'error');
    }
    return new ApiError(`The server returned an error (HTTP ${error.status}). Please try again.`, error.status, 'error');
  }
  return new ApiError('Something unexpected happened. Please try again.', -1, 'unknown');
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  getProviders(): Observable<ProvidersResponse> {
    return this.http.get<ProvidersResponse>(`${API_BASE}/providers`).pipe(catchError((e) => throwError(() => toApiError(e))));
  }

  extract(file: File): Observable<ExtractionResponse> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http
      .post<ExtractionResponse>(`${API_BASE}/documents/extract`, form)
      .pipe(catchError((e) => throwError(() => toApiError(e))));
  }

  analyze(request: AnalyzeRequest): Observable<AnalyzeResponse> {
    return this.http
      .post<AnalyzeResponse>(`${API_BASE}/analyze`, request)
      .pipe(catchError((e) => throwError(() => toApiError(e))));
  }

  draftEmail(request: NegotiationEmailRequest): Observable<NegotiationEmailResponse> {
    return this.http
      .post<NegotiationEmailResponse>(`${API_BASE}/negotiation-email`, request)
      .pipe(catchError((e) => throwError(() => toApiError(e))));
  }
}
