import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('worker portal intake page has no automated WCAG 2.1 A/AA violations', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByLabel('Full name')).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();

  expect(results.violations).toEqual([]);
});
