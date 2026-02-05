import { expect, test } from "@playwright/test";

import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";

const capabilityCode = "documents.delete";

test("admin can update user capabilities", async ({ page, request }) => {
  const baseUrl = getBaseUrl();
  const token = await ensureAuthReady(request);
  const email = `caps-ui-${Date.now()}@example.com`;

  const createResponse = await request.post(`${baseUrl}/api/users`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      email,
      full_name: "Caps UI",
      role: "reception",
      temp_password: "ChangeMe12345!",
    },
  });
  expect(createResponse.ok()).toBeTruthy();
  const createdUser = (await createResponse.json()) as { id: number };

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/users`, { waitUntil: "domcontentloaded" });

  const userSelect = page.getByTestId("capabilities-user-select");
  await expect(userSelect).toBeVisible();
  await userSelect.selectOption(String(createdUser.id));

  const checkbox = page.getByTestId(`capability-checkbox-${capabilityCode}`);
  await expect(checkbox).toBeVisible();
  await expect(checkbox).toBeChecked();

  await checkbox.uncheck();
  await Promise.all([
    page.waitForResponse((res) =>
      res.url().includes(`/api/users/${createdUser.id}/capabilities`) &&
      res.request().method() === "PUT"
    ),
    page.getByTestId("capabilities-save").click(),
  ]);
  await expect(checkbox).not.toBeChecked();

  await page.reload({ waitUntil: "domcontentloaded" });
  const userSelectReload = page.getByTestId("capabilities-user-select");
  await expect(userSelectReload).toBeVisible();
  await userSelectReload.selectOption(String(createdUser.id));
  const checkboxReload = page.getByTestId(`capability-checkbox-${capabilityCode}`);
  await expect(checkboxReload).not.toBeChecked();

  await checkboxReload.check();
  await Promise.all([
    page.waitForResponse((res) =>
      res.url().includes(`/api/users/${createdUser.id}/capabilities`) &&
      res.request().method() === "PUT"
    ),
    page.getByTestId("capabilities-save").click(),
  ]);
  await expect(checkboxReload).toBeChecked();
});
