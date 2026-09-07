import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createPatient } from "./helpers/api";
import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function setup(page: Page, request: APIRequestContext, values: Record<string, unknown> = {}) {
  const id = await createPatient(request, {
    first_name: "Sample", last_name: `Personal ${Date.now()}`,
    date_of_birth: "1985-02-03", address_line1: "12 Example Road", city: "Exampletown", postcode: "AB1 2CD",
  });
  const token = await primePageAuth(page, request);
  const headers = { Authorization: `Bearer ${token}` };
  const response = await request.patch(`${getBaseUrl()}/api/patients/${id}`, { headers, data: values });
  expect(response.ok()).toBeTruthy();
  return { id, headers };
}

async function open(page: Page, id: string) {
  await page.goto(`${getBaseUrl()}/patients/${id}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("patient-personal-details")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("patient-personal-first_name")).toHaveValue("Sample");
}

async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
  const panel = page.getByTestId("patient-personal-details");
  expect(await panel.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
}

test("Personal keeps primary identity and saves each labelled phone independently", async ({ page, request }) => {
  const retained = {
    phone: "020 7946 0011", notes: "Synthetic preserved note", referral_source: "Synthetic referral",
    care_setting: "CLINIC", patient_category: "CLINIC_PRIVATE", primary_contact_name: "Sample Contact",
    primary_contact_phone: "020 7946 0044", primary_contact_relationship: "Daughter",
    visit_address_text: "Synthetic retained visit address", access_notes: "Synthetic retained access note",
    denplan_plan_name: "Synthetic retained plan", denplan_member_no: "SYNTHETIC-ONLY",
  };
  const fixture = await setup(page, request, retained);
  await open(page, fixture.id);
  await expect(page.getByLabel("Primary phone", { exact: true })).toHaveValue("020 7946 0011");
  await expect(page.getByLabel("Mobile phone", { exact: true })).toHaveValue("");
  const fields = {
    phone_label: "Care home", home_phone: "020 7946 0022", home_phone_label: "Home",
    work_phone: "020 7946 0033", work_phone_label: "Reception",
    mobile_phone: "07700 900123", mobile_phone_label: "Daughter",
    email: "sample.personal@example.com", postcode: "AB1 3EF",
  };
  for (const [key, value] of Object.entries(fields)) await page.getByTestId(`patient-personal-${key}`).fill(value);
  const save = page.waitForResponse((response) => response.request().method() === "PATCH" && response.url().endsWith(`/api/patients/${fixture.id}`));
  await page.getByTestId("patient-save-changes").click();
  expect((await save).ok()).toBeTruthy();
  await expect(page.getByTestId("patient-save-changes")).toBeEnabled();
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("patient-personal-details")).toBeVisible({ timeout: 30_000 });
  for (const [key, value] of Object.entries(fields)) await expect(page.getByTestId(`patient-personal-${key}`)).toHaveValue(value);
  await expect(page.getByTestId("patient-header-actions").getByRole("link", { name: "Call", exact: true })).toHaveAttribute("href", "tel:02079460011");
  const response = await request.get(`${getBaseUrl()}/api/patients/${fixture.id}`, { headers: fixture.headers });
  const patient = await response.json();
  expect(patient).toMatchObject({ ...retained, ...fields });
  await page.getByTestId("patient-personal-work_phone").fill("");
  await page.getByTestId("patient-personal-work_phone_label").fill("");
  const clear = page.waitForResponse((r) => r.request().method() === "PATCH" && r.url().endsWith(`/api/patients/${fixture.id}`));
  await page.getByTestId("patient-save-changes").click();
  expect(await (await clear).json()).toMatchObject({ work_phone: null, work_phone_label: null, mobile_phone: "07700 900123" });
});

test("Personal desktop has three compact columns with details on the right in light and dark", async ({ page, request }) => {
  const fixture = await setup(page, request, {
    phone: "020 7946 0011", phone_label: "Care home", mobile_phone: "07700 900123", mobile_phone_label: "Daughter",
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await open(page, fixture.id);
  const output = path.resolve(".run/personal-previews");
  await mkdir(output, { recursive: true });
  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 1000 });
    const details = (await page.getByTestId("patient-personal-details").boundingBox())!;
    const care = (await page.getByTestId("patient-personal-care-column").boundingBox())!;
    const activity = (await page.getByTestId("patient-personal-activity-column").boundingBox())!;
    expect(care.x + care.width).toBeLessThanOrEqual(activity.x);
    expect(activity.x + activity.width).toBeLessThanOrEqual(details.x);
    expect(Math.abs(details.y - care.y)).toBeLessThanOrEqual(1);
    expect(Math.abs(details.y - activity.y)).toBeLessThanOrEqual(1);
    expect(details.width).toBeGreaterThanOrEqual(299);
    expect(details.height).toBeLessThan(750);
    await noOverflow(page);
  }
  await expect(page.getByTestId("patient-personal-details").getByText(/fax/i)).toHaveCount(0);
  await expect(page.getByTestId("patient-personal-notes")).not.toHaveAttribute("open", "");
  for (const theme of ["light", "dark"]) {
    await page.evaluate((value) => { document.documentElement.dataset.theme = value; localStorage.setItem("theme", value); }, theme);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, `personal-${theme}-1280.png`), fullPage: true });
  }
});

test("Personal mobile starts with details and keeps phone labels and existing workflows reachable", async ({ page, request }) => {
  const fixture = await setup(page, request);
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, fixture.id);
  const details = (await page.getByTestId("patient-personal-details").boundingBox())!;
  const care = (await page.getByTestId("patient-personal-care-column").boundingBox())!;
  expect(details.y + details.height).toBeLessThanOrEqual(care.y);
  for (const name of ["phone", "home_phone", "work_phone", "mobile_phone"]) {
    const number = (await page.getByTestId(`patient-personal-${name}`).boundingBox())!;
    const owner = (await page.getByTestId(`patient-personal-${name}_label`).boundingBox())!;
    expect(owner.x).toBeGreaterThan(number.x);
    expect(Math.abs(owner.y - number.y)).toBeLessThanOrEqual(1);
    expect(owner.x + owner.width).toBeLessThanOrEqual(391);
  }
  await noOverflow(page);
  await expect(page.getByTestId("patient-appointments")).toBeVisible();
  await expect(page.getByTestId("patient-personal-activity-column").locator("summary").filter({ hasText: /^Documents$/ })).toBeVisible();
  await expect(page.getByTestId("patient-personal-activity-column").locator("summary").filter({ hasText: /^Attachments$/ })).toBeVisible();
  const output = path.resolve(".run/personal-previews");
  await mkdir(output, { recursive: true });
  await page.getByTestId("patient-personal-details").screenshot({ path: path.join(output, "personal-mobile.png") });
});

test("Personal phone fields stay read-only and a labelled mobile-only number remains callable", async ({ page, request }) => {
  const fixture = await setup(page, request, { phone: null, mobile_phone: "07700 900123", mobile_phone_label: "Daughter" });
  await page.route("**/api/me/capabilities", (route) => route.fulfill({ status: 200, json: ["patients.view"] }));
  let patches = 0;
  page.on("request", (req) => { if (req.method() === "PATCH" && req.url().endsWith(`/api/patients/${fixture.id}`)) patches += 1; });
  await open(page, fixture.id);
  for (const name of ["phone", "phone_label", "home_phone", "home_phone_label", "work_phone", "work_phone_label", "mobile_phone", "mobile_phone_label"]) {
    await expect(page.getByTestId(`patient-personal-${name}`)).toBeDisabled();
  }
  await expect(page.getByTestId("patient-save-changes")).toHaveCount(0);
  const call = page.getByTestId("patient-header-actions").getByRole("link", { name: "Call", exact: true });
  await expect(call).toHaveAttribute("href", "tel:07700900123");
  await expect(call).toHaveAttribute("title", "Mobile phone: 07700 900123 · Daughter");
  await expect(page.getByTestId("patient-header-actions").getByText("No phone", { exact: true })).toHaveCount(0);
  expect(patches).toBe(0);
});
