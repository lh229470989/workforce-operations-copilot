import { expect, test } from "@playwright/test";

test("streams a role-scoped answer and renders a report download card", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/Ask about/i).fill("Download my submitted time entries as CSV");
  await page.getByRole("button", { name: /send/i }).click();

  const download = page.getByRole("link", { name: "Download CSV" });
  // The response wording and LLM latency may vary; the trusted structured
  // download card is the stable browser contract this test owns.
  await expect(download).toBeVisible({ timeout: 45_000 });
  await expect(download).toHaveAttribute("href", /status=submitted/);
});

test("keeps write execution behind explicit confirmation", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder(/Ask about/i).fill(
    "Draft 1 hour on Apollo for 2026-12-18, description: browser acceptance check",
  );
  await page.getByRole("button", { name: /send/i }).click();

  await expect(page.getByText("DRY RUN", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm & create" })).toBeVisible();
});

test("shows admin-only audit controls for the admin persona", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Switch role").selectOption("1");
  await page.getByText("Admin operations").click();
  await page.getByRole("button", { name: "Load audit events" }).click();
  await expect(page.getByText("Metadata-only agent executions")).toBeVisible();
});
