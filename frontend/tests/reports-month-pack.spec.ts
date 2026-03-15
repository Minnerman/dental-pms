import { expect, test, type Page } from "@playwright/test";

import { getBaseUrl, primePageAuth } from "./helpers/auth";

async function waitForReportsPage(page: Page) {
  await expect(page).not.toHaveURL(/\/login|\/change-password/);
  await expect(page.getByRole("heading", { name: "Financial reports" })).toBeVisible({
    timeout: 20_000,
  });
}

async function exerciseMonthPackDownload(
  page: Page,
  format: "pdf" | "zip",
  expectedFilename: string
) {
  const activeButton = page.getByTestId(`reports-month-pack-${format}`);
  const idleButton = page.getByTestId(`reports-month-pack-${format === "pdf" ? "zip" : "pdf"}`);
  const downloadingText = format === "pdf" ? "Downloading PDF..." : "Downloading ZIP...";
  const idleText = format === "pdf" ? "Download PDF" : "Download ZIP";
  const routePattern = new RegExp(`/api/reports/finance/month-pack\\?.*format=${format}(?:&|$)`);

  let seenRequest!: () => void;
  const seenRequestPromise = new Promise<void>((resolve) => {
    seenRequest = resolve;
  });
  let releaseResponse!: () => void;
  const releaseResponsePromise = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });

  await page.route(routePattern, async (route) => {
    seenRequest();
    await releaseResponsePromise;
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": format === "pdf" ? "application/pdf" : "application/zip",
        "Content-Disposition": `attachment; filename="${expectedFilename}"; filename*=UTF-8''ignored-${format}.${format}`,
      },
      body:
        format === "pdf"
          ? Buffer.from("%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")
          : Buffer.from("PK\u0003\u0004month-pack"),
    });
  });

  const downloadPromise = page.waitForEvent("download");
  await activeButton.click();
  await seenRequestPromise;

  await expect(activeButton).toBeDisabled();
  await expect(activeButton).toHaveText(downloadingText);
  await expect(idleButton).toBeDisabled();

  releaseResponse();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(expectedFilename);

  await expect(activeButton).toBeEnabled({ timeout: 15_000 });
  await expect(activeButton).toHaveText(idleText);
  await expect(idleButton).toBeEnabled({ timeout: 15_000 });
  await page.unroute(routePattern);
}

test("financial reports month-pack downloads show in-flight state and honor header filenames", async ({
  page,
  request,
}) => {
  const baseUrl = getBaseUrl();
  const year = new Date().getFullYear();
  const month = "3";

  await primePageAuth(page, request);
  await page.goto(`${baseUrl}/reports`, { waitUntil: "domcontentloaded" });
  await waitForReportsPage(page);

  const monthPackCard = page.locator(".card").filter({ hasText: "Monthly export pack" }).first();
  await monthPackCard.locator("select").nth(0).selectOption(month);
  await monthPackCard.locator("select").nth(1).selectOption(String(year));

  await exerciseMonthPackDownload(page, "pdf", `finance_pack_${year}_03.pdf`);
  await exerciseMonthPackDownload(page, "zip", `finance_pack_${year}_03.zip`);
});
