import { expect, type Locator, type Page } from '@playwright/test'

export function uniqueRequirementTitle(): string {
  return `PW E2E Snake MVP ${Date.now()}`
}

export async function waitForClarifyDialog(page: Page): Promise<void> {
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('MVP Brief Preview')).toBeVisible()
}

export async function extractLabeledValue(page: Page, label: string): Promise<string> {
  const locator = page.locator('p', { hasText: `${label}:` }).first()
  await expect(locator).toBeVisible()
  const text = await locator.textContent()
  if (!text) {
    throw new Error(`Missing text for label: ${label}`)
  }

  const pieces = text.split(':')
  return pieces.slice(1).join(':').trim()
}

export function kickoffTranscriptButton(page: Page): Locator {
  return page.getByRole('button', { name: 'View Meeting Transcript' })
}

export function kickoffDeliveryButton(page: Page): Locator {
  return page.getByRole('button', { name: 'Open Delivery Board' })
}
