import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');
  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Code-Intel/);
});

test('graph explorer loads', async ({ page }) => {
  await page.goto('/');
  // Basic check for the existence of the main container
  const container = page.locator('#root');
  await expect(container).toBeVisible();
});
