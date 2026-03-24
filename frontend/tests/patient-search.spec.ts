import { expect, test } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

test("patients page searches by full and partial patient name and opens the selected record", async ({
  page,
  request,
}) => {
  const unique = Date.now();
  const firstName = `Searchable${unique}`;
  const lastName = `Example${unique}`;
  const distractorFirst = `Other${unique}`;
  const distractorLast = `Patient${unique}`;
  const patientId = await createPatient(request, {
    first_name: firstName,
    last_name: lastName,
  });
  await createPatient(request, {
    first_name: distractorFirst,
    last_name: distractorLast,
  });

  await primePageAuth(page, request);
  await page.goto(`${getBaseUrl()}/patients`, { waitUntil: "domcontentloaded" });

  const searchInput = page.getByPlaceholder("Search name, email, phone");
  const searchButton = page.getByRole("button", { name: "Search" });
  const targetLink = page.getByRole("link", { name: `${firstName} ${lastName}` });
  const distractorLink = page.getByRole("link", { name: `${distractorFirst} ${distractorLast}` });

  await expect(searchInput).toBeVisible({ timeout: 15_000 });
  await expect(searchInput).toBeFocused();

  const fullNameQuery = `${firstName} ${lastName}`;
  await searchInput.fill(fullNameQuery);
  const fullNameResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/patients" &&
      url.searchParams.get("query") === fullNameQuery
    );
  });
  await searchButton.click();
  await fullNameResponse;

  await expect(targetLink).toBeVisible({ timeout: 15_000 });
  await expect(distractorLink).toHaveCount(0);

  const partialNameQuery = lastName.slice(0, Math.min(8, lastName.length));
  await searchInput.fill(partialNameQuery);
  const partialNameResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/patients" &&
      url.searchParams.get("query") === partialNameQuery
    );
  });
  await searchButton.click();
  await partialNameResponse;

  await expect(targetLink).toBeVisible({ timeout: 15_000 });
  await expect(distractorLink).toHaveCount(0);

  await targetLink.click();
  await page.waitForURL(new RegExp(`/patients/${patientId}$`), { timeout: 15_000 });
  await expect(page.getByTestId("patient-header-name")).toContainText(`${firstName} ${lastName}`);
});
