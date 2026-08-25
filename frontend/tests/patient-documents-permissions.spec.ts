import { expect, test, type Page } from "@playwright/test";

import { createPatient } from "./helpers/api";
import { ensureAuthReady, getBaseUrl, primePageAuth } from "./helpers/auth";


async function mockCapabilities(page: Page, capabilities: string[]) {
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(capabilities),
    });
  });
}


async function createDocumentFixture(pageRequest: Parameters<typeof createPatient>[0]) {
  const baseUrl = getBaseUrl();
  const patientId = await createPatient(pageRequest, {
    first_name: "Document",
    last_name: `Permissions ${Date.now()}`,
  });
  const token = await ensureAuthReady(pageRequest);
  const headers = { Authorization: `Bearer ${token}` };
  const templateResponse = await pageRequest.post(`${baseUrl}/api/document-templates`, {
    headers,
    data: {
      name: `Synthetic permission template ${Date.now()}`,
      kind: "letter",
      content: "Synthetic permission document",
      is_active: true,
    },
  });
  expect(templateResponse.ok()).toBeTruthy();
  const template = (await templateResponse.json()) as { id: number };
  const documentResponse = await pageRequest.post(
    `${baseUrl}/api/patients/${patientId}/documents`,
    {
      headers,
      data: { template_id: template.id, title: "Synthetic permission document" },
    }
  );
  expect(documentResponse.ok()).toBeTruthy();
  const document = (await documentResponse.json()) as { id: number };
  const attachmentResponse = await pageRequest.post(
    `${baseUrl}/api/patients/${patientId}/attachments`,
    {
      headers,
      multipart: {
        file: {
          name: "synthetic-permission.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from("synthetic"),
        },
      },
    }
  );
  expect(attachmentResponse.ok()).toBeTruthy();
  const attachment = (await attachmentResponse.json()) as { id: number };
  return { patientId, documentId: document.id, attachmentId: attachment.id };
}


test("document download capability gives read-only patient documents and attachments", async ({
  page,
  request,
}) => {
  const fixture = await createDocumentFixture(request);
  await primePageAuth(page, request);
  await mockCapabilities(page, ["patients.view", "documents.download"]);

  await page.goto(`${getBaseUrl()}/patients/${fixture.patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });
  const documentAccess = page.getByTestId("patient-documents-access");
  await expect(documentAccess).toHaveAttribute("data-state", "read-only");
  await expect(page.getByTestId(`patient-document-card-${fixture.documentId}`)).toBeVisible();
  await expect(
    page.getByTestId(`patient-document-download-text-${fixture.documentId}`)
  ).toBeVisible();
  await expect(page.getByTestId("patient-document-save")).toHaveCount(0);
  await expect(page.getByTestId(`patient-document-attach-pdf-${fixture.documentId}`)).toHaveCount(0);
  await expect(page.getByTestId(`patient-document-delete-${fixture.documentId}`)).toHaveCount(0);

  await page.goto(`${getBaseUrl()}/patients/${fixture.patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });
  const attachmentAccess = page.getByTestId("patient-attachments-access");
  await expect(attachmentAccess).toHaveAttribute("data-state", "read-only");
  await expect(page.getByTestId(`attachment-card-${fixture.attachmentId}`)).toBeVisible();
  await expect(page.getByTestId(`attachment-download-${fixture.attachmentId}`)).toBeVisible();
  await expect(page.getByTestId("attachment-upload")).toHaveCount(0);
  await expect(page.getByTestId(`attachment-delete-${fixture.attachmentId}`)).toHaveCount(0);
});


test("document write and delete controls follow effective capabilities, not role", async ({
  page,
  request,
}) => {
  const fixture = await createDocumentFixture(request);
  await primePageAuth(page, request);
  await mockCapabilities(page, [
    "patients.view",
    "documents.download",
    "documents.upload",
    "documents.delete",
  ]);

  await page.goto(`${getBaseUrl()}/patients/${fixture.patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("patient-documents-access")).toHaveAttribute(
    "data-state",
    "write"
  );
  await expect(page.getByTestId("patient-document-save")).toBeVisible();
  await expect(page.getByTestId(`patient-document-attach-pdf-${fixture.documentId}`)).toBeVisible();
  await expect(page.getByTestId(`patient-document-delete-${fixture.documentId}`)).toBeVisible();

  await page.goto(`${getBaseUrl()}/patients/${fixture.patientId}/attachments`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("patient-attachments-access")).toHaveAttribute(
    "data-state",
    "write"
  );
  await expect(page.getByTestId("attachment-upload")).toBeVisible();
  await expect(page.getByTestId(`attachment-delete-${fixture.attachmentId}`)).toBeVisible();
});


test("capability verification failure blocks document content and mutation controls safely", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: `Capability Failure ${Date.now()}`,
  });
  const privateResponse = "private backend response must not render";
  await primePageAuth(page, request);
  await page.route("**/api/me/capabilities", async (route) => {
    await route.fulfill({
      status: 503,
      headers: { "Content-Type": "text/html" },
      body: privateResponse,
    });
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("patient-documents-access")).toHaveAttribute(
    "data-state",
    "denied"
  );
  await expect(page.getByText("Patient permissions could not be verified.")).toBeVisible();
  await expect(page.getByTestId("patient-document-save")).toHaveCount(0);
  await expect(page.getByText(privateResponse)).toHaveCount(0);
});


test("document API failures use fixed safe messages without response bodies", async ({
  page,
  request,
}) => {
  const patientId = await createPatient(request, {
    first_name: "Document",
    last_name: `Safe Error ${Date.now()}`,
  });
  const privateResponse = "private exception and internal path";
  await primePageAuth(page, request);
  await mockCapabilities(page, ["patients.view", "documents.download"]);
  await page.route(new RegExp(`/api/patients/${patientId}/documents$`), async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 500,
      headers: { "Content-Type": "text/html" },
      body: privateResponse,
    });
  });

  await page.goto(`${getBaseUrl()}/patients/${patientId}/documents`, {
    waitUntil: "domcontentloaded",
  });
  await expect(
    page.getByText("The document service is temporarily unavailable. Try again later.")
  ).toBeVisible();
  await expect(page.getByText(privateResponse)).toHaveCount(0);
});
