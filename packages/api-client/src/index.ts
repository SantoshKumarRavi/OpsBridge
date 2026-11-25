import type { components, paths } from './openapi.generated.js';

type ListCasesOperation = NonNullable<paths['/cases']['get']>;
type CaseListQuery = NonNullable<NonNullable<ListCasesOperation['parameters']['query']>>;
type DecideCaseOperation = NonNullable<paths['/cases/{caseId}/decision']['post']>;

export type CaseStatus = NonNullable<CaseListQuery['status']>;
export type OnboardingCase = components['schemas']['OnboardingCase'];
export type CasePage = components['schemas']['CaseList'];
export type CreateCaseInput = Pick<components['schemas']['CreateCaseRequest'], 'workerName' | 'email'>
  & Partial<Pick<components['schemas']['CreateCaseRequest'], 'phone' | 'role' | 'country'>>;
export type UploadDocumentResult = components['schemas']['UploadDocumentResponse'];
export type CaseDecisionInput = DecideCaseOperation['requestBody']['content']['application/json'];

export interface OpsBridgeClientOptions {
  baseUrl: string;
  getHeaders?: () => HeadersInit | Promise<HeadersInit>;
  fetch?: typeof globalThis.fetch;
}

export class OpsBridgeApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = 'OpsBridgeApiError';
    this.status = status;
    this.body = body;
  }
}

export class OpsBridgeClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof globalThis.fetch;
  private readonly options: OpsBridgeClientOptions;

  constructor(options: OpsBridgeClientOptions) {
    this.options = options;
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
    this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async listCases(query: CaseListQuery = {}): Promise<CasePage> {
    const params = new URLSearchParams();
    if (query.status) params.set('status', query.status);
    if (query.limit !== undefined) params.set('limit', String(query.limit));
    if (query.cursor) params.set('cursor', query.cursor);
    const suffix = params.size ? `?${params}` : '';
    return this.request(`/cases${suffix}`);
  }

  createCase(input: CreateCaseInput): Promise<OnboardingCase> {
    return this.request('/cases', { method: 'POST', body: JSON.stringify(input) });
  }

  getCase(caseId: string): Promise<OnboardingCase> {
    return this.request(`/cases/${encodeURIComponent(caseId)}`);
  }

  decideCase(caseId: string, input: CaseDecisionInput): Promise<OnboardingCase> {
    return this.request(`/cases/${encodeURIComponent(caseId)}/decision`, { method: 'POST', body: JSON.stringify(input) });
  }

  uploadDocument(caseId: string, file: Blob, filename: string, documentType = 'identity'): Promise<UploadDocumentResult> {
    const body = new FormData();
    body.append('file', file, filename);
    body.append('documentType', documentType);
    return this.request(`/cases/${encodeURIComponent(caseId)}/documents`, { method: 'POST', body });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(await this.options.getHeaders?.());
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, { ...init, headers });
    if (!response.ok) {
      let body: unknown;
      try { body = await response.json(); } catch { body = await response.text(); }
      throw new OpsBridgeApiError(`OpsBridge API request failed (${response.status})`, response.status, body);
    }
    return response.json() as Promise<T>;
  }
}

export function createOpsBridgeClient(options: OpsBridgeClientOptions): OpsBridgeClient {
  return new OpsBridgeClient(options);
}
