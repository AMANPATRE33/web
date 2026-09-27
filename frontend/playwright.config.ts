import { defineConfig, devices } from "@playwright/test";

/**
 * Visual QA configuration.
 *
 * Scoped to `qa/` only, so `npm test` (Vitest, unit) and this (real browser)
 * stay separate. `forbidOnly` because a stray `.only` silently reduces the sweep
 * to one route at five viewports, which looks like a pass.
 */
export default defineConfig({
  testDir: "./qa",
  testMatch: /.*\.spec\.ts/,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.QA_BASE_URL ?? "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
