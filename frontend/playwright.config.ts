import { defineConfig } from "@playwright/test";

const envBase = process.env.FRONTEND_BASE_URL;
const baseURL =
  envBase && !envBase.includes("${")
    ? envBase
    : `http://localhost:${process.env.FRONTEND_PORT ?? "3100"}`;

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL,
    headless: true,
  },
});
