import { expect, test } from '@playwright/test';

test('worker can complete the first onboarding step using only the keyboard', async ({ page }) => {
  await page.route('**/api/v1/cases', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const submitted = route.request().postDataJSON();
    expect(submitted).toMatchObject({
      workerName: 'Keyboard Navigation Worker',
      email: 'keyboard@example.invalid',
      phone: '+10000000000',
      role: 'Keyboard Tester',
      country: 'US',
    });
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ id: 'c2a5f6e9-4a1f-4e6e-a6f2-802d990a3a2a' }),
    });
  });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Let’s get you ready to work.' })).toBeVisible();

  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Full name')).toBeFocused();
  await page.keyboard.type('Keyboard Navigation Worker');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Email address')).toBeFocused();
  await page.keyboard.type('keyboard@example.invalid');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Phone number')).toBeFocused();
  await page.keyboard.type('+10000000000');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Role')).toBeFocused();
  await page.keyboard.type('Keyboard Tester');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Country')).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByLabel('Country')).toHaveValue('US');
  await page.keyboard.press('Tab');

  const submit = page.getByRole('button', { name: /Save and continue/ });
  await expect(submit).toBeFocused();
  await page.keyboard.press('Enter');

  await expect(page.getByRole('status')).toContainText(
    'Application received. Reference: c2a5f6e9-4a1f-4e6e-a6f2-802d990a3a2a',
  );
  await expect(page.getByRole('heading', { name: 'Add your verification document.' })).toBeVisible();
  await expect(page.getByLabel('Choose document')).toBeVisible();
});
