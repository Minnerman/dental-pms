import { expect, test } from "@playwright/test";

import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

test("templates page create shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);
  const templateName = `Templates Create Proof ${unique}`;
  const templateContent = `Templates create proof body ${unique}`;

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/templates`, {
    waitUntil: "domcontentloaded",
  });

  const nameField = page.getByTestId("template-create-name");
  const contentField = page.getByTestId("template-create-content");
  const createButton = page.getByTestId("template-create-submit");

  await expect(nameField).toBeVisible({ timeout: 15_000 });
  await expect(contentField).toBeVisible({ timeout: 15_000 });
  await expect(createButton).toBeEnabled();

  await nameField.fill(templateName);
  await contentField.fill(templateContent);

  const templateRoutePattern = new RegExp("/api/document-templates$");
  let requestCount = 0;
  let seenCreateRequest!: () => void;
  const seenCreateRequestPromise = new Promise<void>((resolve) => {
    seenCreateRequest = resolve;
  });
  let releaseCreateRequest!: () => void;
  const releaseCreateRequestPromise = new Promise<void>((resolve) => {
    releaseCreateRequest = resolve;
  });

  await page.route(templateRoutePattern, async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenCreateRequest();
      await releaseCreateRequestPromise;
    }
    await route.continue();
  });

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/document-templates")
  );

  const clickState = await createButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Create template button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenCreateRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(createButton).toBeDisabled();
  await expect(createButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseCreateRequest();

  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  expect(createResponse.request().postDataJSON()).toMatchObject({
    name: templateName,
    kind: "letter",
    content: templateContent,
    is_active: true,
  });
  const createdTemplate = (await createResponse.json()) as { id: number };
  await page.unroute(templateRoutePattern);

  await expect(createButton).toBeEnabled({ timeout: 15_000 });
  await expect(createButton).toHaveText("Create template");
  await expect(nameField).toHaveValue("");
  await expect(contentField).toHaveValue("");
  await expect(page.getByTestId(`template-row-${createdTemplate.id}`)).toBeVisible({
    timeout: 15_000,
  });

  const verifyResponse = await request.get(`${baseUrl}/api/document-templates?include_inactive=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const templates = (await verifyResponse.json()) as Array<{ id: number; name: string }>;
  expect(templates.some((template) => template.id === createdTemplate.id && template.name === templateName)).toBeTruthy();
});

test("templates page edit save shows in-flight state and guards repeat submit", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);
  const originalName = `Templates Edit Proof ${unique}`;
  const updatedName = `Templates Edit Updated ${unique}`;
  const updatedContent = `Templates edit updated body ${unique}`;

  const templateResponse = await request.post(`${baseUrl}/api/document-templates`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: originalName,
      kind: "letter",
      content: "Templates edit original body",
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
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByRole("button", { name: originalName }).click();

  const nameField = page.getByTestId("template-edit-name");
  const contentField = page.getByTestId("template-edit-content");
  const saveButton = page.getByTestId("template-edit-submit");

  await expect(nameField).toBeVisible({ timeout: 15_000 });
  await expect(contentField).toBeVisible({ timeout: 15_000 });
  await expect(saveButton).toBeEnabled();

  await nameField.fill(updatedName);
  await contentField.fill(updatedContent);

  const templateRoutePattern = new RegExp(`/api/document-templates/${template.id}$`);
  let requestCount = 0;
  let seenEditRequest!: () => void;
  const seenEditRequestPromise = new Promise<void>((resolve) => {
    seenEditRequest = resolve;
  });
  let releaseEditRequest!: () => void;
  const releaseEditRequestPromise = new Promise<void>((resolve) => {
    releaseEditRequest = resolve;
  });

  await page.route(templateRoutePattern, async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.continue();
      return;
    }
    requestCount += 1;
    if (requestCount === 1) {
      seenEditRequest();
      await releaseEditRequestPromise;
    }
    await route.continue();
  });

  const editResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().endsWith(`/api/document-templates/${template.id}`)
  );

  const clickState = await saveButton.evaluate((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error("Template edit save button not found");
    }
    const beforeDisabled = button.disabled;
    button.click();
    const afterFirstDisabled = button.disabled;
    button.click();
    return { beforeDisabled, afterFirstDisabled, afterSecondDisabled: button.disabled };
  });
  await seenEditRequestPromise;

  expect(clickState.beforeDisabled).toBe(false);
  expect(clickState.afterFirstDisabled).toBe(true);
  expect(clickState.afterSecondDisabled).toBe(true);
  await expect(saveButton).toBeDisabled();
  await expect(saveButton).toHaveText("Saving...");
  await page.waitForTimeout(250);
  expect(requestCount).toBe(1);

  releaseEditRequest();

  const editResponse = await editResponsePromise;
  expect(editResponse.ok()).toBeTruthy();
  expect(editResponse.request().postDataJSON()).toMatchObject({
    name: updatedName,
    kind: "letter",
    content: updatedContent,
    is_active: true,
  });
  await page.unroute(templateRoutePattern);

  await expect(saveButton).toBeEnabled({ timeout: 15_000 });
  await expect(saveButton).toHaveText("Save changes");
  await expect(nameField).toHaveValue(updatedName);
  await expect(contentField).toHaveValue(updatedContent);
  await expect(row.getByRole("button", { name: updatedName })).toBeVisible({
    timeout: 15_000,
  });

  const verifyResponse = await request.get(`${baseUrl}/api/document-templates?include_inactive=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(verifyResponse.ok()).toBeTruthy();
  const templates = (await verifyResponse.json()) as Array<{ id: number; name: string; content: string }>;
  expect(
    templates.some(
      (savedTemplate) =>
        savedTemplate.id === template.id &&
        savedTemplate.name === updatedName &&
        savedTemplate.content === updatedContent
    )
  ).toBeTruthy();
});
