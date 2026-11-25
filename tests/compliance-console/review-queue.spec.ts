import { expect, test } from '@playwright/test';

test('reviewer records a final case decision through the typed client', async ({ page }) => {
  let decisionBody: Record<string, unknown> | undefined;
  let decisionSaved = false;
  let queueRequestSeen = false;
  const reviewCase = {
    id: 'case-123',
    tenant_id: 'demo-tenant',
    worker_name: 'Ananya Rao',
    email: 'ananya@example.test',
    phone: '',
    role: 'Operations Associate',
    country: 'IN',
    status: 'review_required',
    created_at: '2026-11-20T09:00:00Z',
    updated_at: '2026-11-20T09:00:00Z',
    documents: [{ warnings: ['Name mismatch requires human review'] }],
    audit_events: [],
  };

  await page.route(url => url.pathname === '/api/v1/cases' && url.searchParams.get('status') === 'review_required', route => {
    queueRequestSeen = true;
    return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ items: decisionSaved ? [] : [reviewCase], total: decisionSaved ? 0 : 1, next_cursor: null }),
    });
  });
  await page.route('**/api/v1/cases/case-123/decision', async route => {
    decisionBody = route.request().postDataJSON();
    decisionSaved = true;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...reviewCase, status: 'approved' }) });
  });

  await page.goto('/');
  await expect(page.getByText('Ananya Rao')).toBeVisible();
  await expect(page.getByText('Name mismatch requires human review')).toBeVisible();
  page.once('dialog', dialog => dialog.accept('Identity evidence verified'));
  await page.getByRole('button', { name: 'Approve' }).click();
  await expect(page.getByText('Decision recorded for Ananya Rao.')).toBeVisible();
  await expect(page.getByText('No cases are awaiting review.')).toBeVisible();
  expect(decisionBody).toEqual({ decision: 'approve', reason: 'Identity evidence verified' });
  expect(queueRequestSeen).toBe(true);
});
