import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('reviewer loads a saved grant, records suppression, and sees the blocked eligibility result', async ({ page }) => {
  let recordedPolicy: Record<string, unknown> | undefined;
  await page.route('**/api/v1/cases?status=review_required', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ items: [] }),
  }));
  await page.route('**/api/v1/voice/contacts**', async route => {
    if (route.request().method() === 'PUT') {
      recordedPolicy = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(recordedPolicy) });
      return;
    }
    if (route.request().url().includes('/eligibility')) {
      const blocked = recordedPolicy?.suppressed === true;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ eligible: !blocked, reason: blocked ? 'suppressed' : 'eligible' }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        phoneNumber: '+12025550100', consentStatus: 'granted', consentRecordedAt: '2026-11-20T09:15:00Z',
        consentSource: 'Signed onboarding form', consentReference: 'evidence-ref-42', suppressed: false, suppressionReason: '',
      }),
    });
  });

  await page.goto('/');
  const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.getByLabel('Phone number in E.164 format').fill('+12025550100');
  await page.getByRole('button', { name: 'Load saved policy' }).click();
  await expect(page.getByLabel('Consent status')).toHaveValue('granted');
  await expect(page.getByLabel('Consent source')).toHaveValue('Signed onboarding form');
  await page.getByLabel('Suppress this number from outbound calls').check();
  await page.getByLabel('Suppression reason').fill('Customer requested no calls');
  await page.getByRole('button', { name: 'Save audited policy' }).click();

  await expect(page.getByText('Voice contact policy saved and audited.')).toBeVisible();
  await expect(page.getByText('Not eligible for outbound calling: suppressed.')).toBeVisible();
  expect(recordedPolicy).toMatchObject({
    phoneNumber: '+12025550100',
    consentStatus: 'granted',
    consentSource: 'Signed onboarding form',
    consentReference: 'evidence-ref-42',
    suppressed: true,
    suppressionReason: 'Customer requested no calls',
  });
  expect(recordedPolicy?.consentRecordedAt).toEqual(expect.stringMatching(/^2026-11-20T/));
});
