import { Buffer } from 'node:buffer';
import { expect, test } from '@playwright/test';

type OnboardingCaseResponse = {
  status: string;
  ai_recommendation: {
    suggested_next_step: string;
    human_decision_required: boolean;
  };
  documents: Array<{ status: string }>;
  audit_events: Array<{ event_type: string; correlation_id: string }>;
};

test('worker creates a case and the mock AI fallback routes its document to human review', async ({ page }) => {
  const runId = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const apiBase = (globalThis as any).process?.env?.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080/api/v1';
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Let’s get you ready to work.' })).toBeVisible();
  await page.getByLabel('Full name').fill(`E2E Synthetic Worker ${runId}`);
  await page.getByLabel('Email address').fill(`synthetic-${runId}@example.invalid`);
  await page.getByLabel('Phone number').fill('+10000000000');
  await page.getByLabel('Role').fill('E2E Portfolio Tester');
  await page.getByLabel('Country').selectOption('US');
  await page.getByRole('button', { name: 'Save and continue' }).click();

  const created = page.getByRole('status').filter({ hasText: 'Application received. Reference:' });
  await expect(created).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Add your verification document.' })).toBeVisible();
  const createdMessage = await created.textContent();
  const caseId = createdMessage?.split('Reference:')[1]?.trim();
  if (!caseId) throw new Error('The case creation response did not include a case reference.');

  await page.getByLabel('Choose document').setInputFiles({
    name: 'synthetic-onboarding-e2e.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Synthetic test fixture. Name: Example Worker. Document: DEMO-0001.'),
  });
  await page.getByRole('button', { name: 'Upload for secure review' }).click();
  await expect(page.getByRole('status')).toContainText('Document queued for processing. Status: queued');

  let processedCase: OnboardingCaseResponse | undefined;
  await expect.poll(async () => {
    const response = await page.request.get(`${apiBase}/cases/${caseId}`, {
      headers: { 'X-Tenant-Id': 'demo-tenant' },
    });
    if (!response.ok()) return `HTTP ${response.status()}`;
    processedCase = await response.json() as OnboardingCaseResponse;
    return processedCase.status;
  }, { timeout: 90_000, intervals: [1000, 2000, 5000] }).toBe('review_required');

  expect(processedCase?.ai_recommendation).toMatchObject({
    suggested_next_step: 'request_changes',
    human_decision_required: true,
  });
  expect(processedCase?.documents).toHaveLength(1);
  expect(processedCase?.documents[0].status).toBe('review_required');

  const events = processedCase?.audit_events ?? [];
  const uploadEvent = events.find((event) => event.event_type === 'document.received');
  expect(uploadEvent?.correlation_id).toMatch(/^[0-9a-f-]{36}$/);
  for (const eventType of ['document.processed', 'case.ai_recommendation_updated']) {
    const event = events.find((candidate) => candidate.event_type === eventType);
    expect(event?.correlation_id).toBe(uploadEvent?.correlation_id);
  }
});
