import { expect, test } from '@playwright/test';

test('worker portal creates a case through the gateway and compliance API', async ({ page }) => {
  const runId = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Let’s get you ready to work.' })).toBeVisible();

  await page.getByLabel('Full name').fill(`Browser Contract Worker ${runId}`);
  await page.getByLabel('Email address').fill(`browser-${runId}@example.invalid`);
  await page.getByLabel('Phone number').fill('+10000000000');
  await page.getByLabel('Role').fill('Browser Contract Tester');
  await page.getByLabel('Country').selectOption('US');

  const createResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/cases') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Save and continue' }).click();
  const createResponse = await createResponsePromise;

  expect(createResponse.status()).toBe(201);
  const correlationId = createResponse.headers()['x-correlation-id'];
  expect(correlationId).toMatch(/^[0-9a-f-]{36}$/);
  const createdCase = await createResponse.json();
  expect(createdCase).toMatchObject({
    worker_name: `Browser Contract Worker ${runId}`,
    tenant_id: 'demo-tenant',
    country: 'US',
    status: 'submitted',
  });
  expect(createdCase.audit_events).toEqual(expect.arrayContaining([
    expect.objectContaining({ event_type: 'case.created', correlation_id: correlationId }),
  ]));

  await expect(page.getByRole('status')).toContainText(`Reference: ${createdCase.id}`);
  await expect(page.getByRole('heading', { name: 'Add your verification document.' })).toBeVisible();
});
