import { expect, type Locator, type Page } from '@playwright/test'

type QueryRoot = Page | Locator

export function uniqueRequirementTitle(): string {
  return `PW E2E Snake MVP ${Date.now()}`
}

export async function waitForClarifyDialog(page: Page): Promise<void> {
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('MVP Brief Preview')).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Start Meeting' })).toBeVisible()
}

export async function extractLabeledValue(scope: QueryRoot, label: string): Promise<string> {
  const row = scope.locator('p').filter({ hasText: `${label}:` }).first()
  await expect(row).toBeVisible()
  const text = (await row.textContent())?.trim()
  if (!text) {
    throw new Error(`Missing text for label: ${label}`)
  }

  const [actualLabel, ...rest] = text.split(':')
  if (actualLabel.trim() !== label) {
    throw new Error(`Unexpected label. Expected "${label}", got "${actualLabel.trim()}"`)
  }

  const value = rest.join(':').trim()
  if (!value) {
    throw new Error(`Missing value for label: ${label}`)
  }

  return value
}

export function kickoffTranscriptButton(page: Page): Locator {
  return page.getByRole('button', { name: 'View Meeting Transcript' })
}

export function kickoffDeliveryButton(page: Page): Locator {
  return page.getByRole('button', { name: 'Open Delivery Board' })
}
