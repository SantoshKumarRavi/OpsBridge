import assert from 'node:assert/strict';
import test from 'node:test';
import { createOpsBridgeClient, OpsBridgeApiError } from '../src/index.ts';

test('listCases serializes filters and attaches dynamic auth headers', async () => {
  let requestUrl = '';
  let requestHeaders: Headers | undefined;
  const client = createOpsBridgeClient({
    baseUrl: 'https://api.example.test/api/v1/',
    getHeaders: () => ({ Authorization: 'Bearer fresh-token', 'X-Tenant-Id': 'tenant-a' }),
    fetch: async (input, init) => {
      requestUrl = String(input);
      requestHeaders = new Headers(init?.headers);
      return Response.json({ items: [], total: 0, next_cursor: null });
    },
  });

  const result = await client.listCases({ status: 'processing', limit: 25, cursor: 'next page' });
  assert.equal(requestUrl, 'https://api.example.test/api/v1/cases?status=processing&limit=25&cursor=next+page');
  assert.equal(requestHeaders?.get('authorization'), 'Bearer fresh-token');
  assert.deepEqual(result, { items: [], total: 0, next_cursor: null });
});

test('createCase posts JSON', async () => {
  let requestInit: RequestInit | undefined;
  const client = createOpsBridgeClient({
    baseUrl: 'http://localhost:8080/api/v1',
    fetch: async (_input, init) => { requestInit = init; return Response.json({ id: 'case-1' }, { status: 201 }); },
  });
  await client.createCase({ workerName: 'Asha Rao', email: 'asha@example.test' });
  assert.equal(requestInit?.method, 'POST');
  assert.equal(new Headers(requestInit?.headers).get('content-type'), 'application/json');
  assert.deepEqual(JSON.parse(String(requestInit?.body)), { workerName: 'Asha Rao', email: 'asha@example.test' });
});

test('uploadDocument sends multipart data without setting a boundary manually', async () => {
  let requestInit: RequestInit | undefined;
  const client = createOpsBridgeClient({
    baseUrl: 'http://localhost:8080/api/v1',
    fetch: async (_input, init) => { requestInit = init; return Response.json({ id: 'doc-1', caseId: 'case/a', status: 'queued' }); },
  });
  await client.uploadDocument('case/a', new Blob(['synthetic']), 'proof.txt', 'proof');
  assert.equal(requestInit?.method, 'POST');
  assert.equal(new Headers(requestInit?.headers).has('content-type'), false);
  assert.ok(requestInit?.body instanceof FormData);
  assert.equal((requestInit?.body as FormData).get('documentType'), 'proof');
});

test('decideCase posts a typed human decision to the encoded case route', async () => {
  let requestUrl = '';
  let requestInit: RequestInit | undefined;
  const client = createOpsBridgeClient({
    baseUrl: 'http://localhost:8080/api/v1',
    fetch: async (input, init) => { requestUrl = String(input); requestInit = init; return Response.json({ id: 'case/a' }); },
  });
  await client.decideCase('case/a', { decision: 'approve', reason: 'Evidence verified' });
  assert.equal(requestUrl, 'http://localhost:8080/api/v1/cases/case%2Fa/decision');
  assert.equal(requestInit?.method, 'POST');
  assert.deepEqual(JSON.parse(String(requestInit?.body)), { decision: 'approve', reason: 'Evidence verified' });
});

test('non-2xx responses become typed API errors', async () => {
  const client = createOpsBridgeClient({
    baseUrl: 'http://localhost:8080/api/v1',
    fetch: async () => Response.json({ detail: 'not found' }, { status: 404 }),
  });
  await assert.rejects(client.getCase('missing'), (error: unknown) => {
    assert.ok(error instanceof OpsBridgeApiError);
    assert.equal(error.status, 404);
    assert.deepEqual(error.body, { detail: 'not found' });
    return true;
  });
});
