import { expect, test } from "@playwright/test";

import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("templates page delete shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);
  const templateName = `Templates Delete Proof ${unique}`;

  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: templateName,
      kind: "letter",
      content: "Templates delete proof body",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/templates`, {
    waitUntil: "domcontentloaded",
  });

  const row = page.getByTestId(`template-row-${template.id}`);
  const deleteButton = page.getByTestId(`template-delete-${template.id}`);
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(deleteButton).toBeVisible();

  await page.evaluate(() => {
    window.confirm = () => true;
  });

  let requestCount = 0;
  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseDeleteRequest!: () => void;
  const releaseDeleteRequestPromise = new Promise<void>((resolve) => {
    releaseDeleteRequest = resolve;
  });
  const routePattern = new RegExp(`/api/document-templates/${template.id}$`);

  await page.route(routePattern, async (route, routedRequest) => {
    if (routedRequest.method() !== "DELETE") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenRequest();
    }
    await releaseDeleteRequestPromise;
    await route.continue();
  });

  const clickState = await page.evaluate((id) => {
    const button = document.querySelector(`[data-testid="template-delete-${id}"]`);
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Template delete button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  }, template.id);
  await seenRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(deleteButton).toBeDisabled();
  await expect(deleteButton).toHaveText("Deleting...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseDeleteRequest();

  await expect(row).toHaveCount(0, { timeout: 15_000 });
  await page.unroute(routePattern);

  const verifyResponse = await request.get(`${baseUrl}/api/document-templates?include_inactive=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const templates = (await verifyResponse.json()) as Array<{ id: number; name: string }>;
  expect(templates.some((savedTemplate) => savedTemplate.id === template.id)).toBeFalsy();
});
