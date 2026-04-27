# Real Web E2E: Kickoff To Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real Playwright browser test that drives the web UI from MVP clarification through kickoff and delivery, then verifies transcript and delivery artifacts through backend APIs.

**Architecture:** The implementation adds Playwright only under `web/`, keeps the user responsible for starting frontend/backend services, and combines browser actions with API helper assertions. The suite uses one primary happy-path spec and captures rich failure artifacts for debugging real Claude-backed failures.

**Tech Stack:** Playwright, TypeScript, Vite frontend, FastAPI backend, real Claude-backed kickoff/delivery APIs

---

## File Structure

- Create: `web/playwright.config.ts`
  - Playwright config with base URL, trace/screenshots, and long timeouts for real kickoff flow.
- Create: `web/e2e/kickoff-to-delivery.spec.ts`
  - Main end-to-end happy-path browser test.
- Create: `web/e2e/helpers/api.ts`
  - Small helpers for transcript and delivery board verification.
- Create: `web/e2e/helpers/selectors.ts`
  - Shared selectors and UI helpers to keep the main spec readable.
- Modify: `web/package.json`
  - Add Playwright test scripts.
- Modify: `docs/frontend-mvp-cycle.md`
  - Add a short section describing how to run the new real browser E2E check.

## Task 1: Add Playwright Tooling

**Files:**
- Modify: `web/package.json`
- Create: `web/playwright.config.ts`

- [ ] **Step 1: Add Playwright dev dependency and scripts to `web/package.json`**

Add the following entries:

```json
{
  "scripts": {
    "generate-types": "node scripts/generate-types.js",
    "dev": "npm run generate-types && vite",
    "build": "tsc && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "e2e": "playwright test",
    "e2e:headed": "playwright test --headed",
    "e2e:debug": "playwright test --debug"
  },
  "devDependencies": {
    "@eslint/js": "^9.17.0",
    "@playwright/test": "^1.55.0",
    "@types/react": "^18.3.18"
  }
}
```

- [ ] **Step 2: Install the dependency**

Run:

```powershell
npm --prefix web install
```

Expected:
- `package-lock.json` updates
- `@playwright/test` appears in `web/package.json`

- [ ] **Step 3: Create `web/playwright.config.ts`**

Use this config:

```ts
import { defineConfig } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173'

export default defineConfig({
  testDir: './e2e',
  timeout: 10 * 60 * 1000,
  expect: {
    timeout: 30 * 1000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
})
```

- [ ] **Step 4: Run a config smoke check**

Run:

```powershell
npm --prefix web run e2e -- --list
```

Expected:
- Playwright loads config successfully
- No test execution yet

- [ ] **Step 5: Commit**

```powershell
git add web/package.json web/package-lock.json web/playwright.config.ts
git commit -m "test: add Playwright tooling"
```

## Task 2: Add API Verification Helpers

**Files:**
- Create: `web/e2e/helpers/api.ts`

- [ ] **Step 1: Write the helper file**

Create this file:

```ts
export interface MeetingTranscriptEvent {
  agent_role?: string
  message?: string
}

export interface MeetingTranscriptResponse {
  meeting_id: string
  events: MeetingTranscriptEvent[]
}

export interface DeliveryBoardResponse {
  decision_gates: Array<{ id: string; status: string }>
  tasks: Array<{ id: string; status: string }>
}

const apiBaseUrl = process.env.E2E_API_URL ?? 'http://127.0.0.1:8000'
const workspace = process.env.E2E_WORKSPACE ?? '.'

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) {
    throw new Error(`Request failed ${response.status}: ${path}`)
  }
  return (await response.json()) as T
}

export async function fetchTranscript(meetingId: string): Promise<MeetingTranscriptResponse> {
  return fetchJson<MeetingTranscriptResponse>(
    `/api/meetings/${meetingId}/transcript?workspace=${encodeURIComponent(workspace)}`,
  )
}

export async function fetchDeliveryBoard(): Promise<DeliveryBoardResponse> {
  return fetchJson<DeliveryBoardResponse>(
    `/api/delivery-board?workspace=${encodeURIComponent(workspace)}`,
  )
}
```

- [ ] **Step 2: Sanity-check the helper file with TypeScript build**

Run:

```powershell
npm --prefix web run build
```

Expected:
- Build passes
- No TypeScript errors from the new helper

- [ ] **Step 3: Commit**

```powershell
git add web/e2e/helpers/api.ts
git commit -m "test: add E2E API verification helpers"
```

## Task 3: Add Shared UI Selectors And Parsing Helpers

**Files:**
- Create: `web/e2e/helpers/selectors.ts`

- [ ] **Step 1: Create the selector helper file**

Create this file:

```ts
import { expect, type Locator, type Page } from '@playwright/test'

export function uniqueRequirementTitle(): string {
  return `PW E2E Snake MVP ${Date.now()}`
}

export async function waitForClarifyDialog(page: Page): Promise<void> {
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('MVP Brief Preview')).toBeVisible()
}

export async function extractLabeledValue(page: Page, label: string): Promise<string> {
  const locator = page.locator(`text=${label}`).first()
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
```

- [ ] **Step 2: Run build to verify helper typing**

Run:

```powershell
npm --prefix web run build
```

Expected:
- Build passes

- [ ] **Step 3: Commit**

```powershell
git add web/e2e/helpers/selectors.ts
git commit -m "test: add E2E selector helpers"
```

## Task 4: Implement The Real Kickoff-To-Delivery Spec

**Files:**
- Create: `web/e2e/kickoff-to-delivery.spec.ts`
- Test: `web/e2e/kickoff-to-delivery.spec.ts`

- [ ] **Step 1: Write the failing spec**

Create this file:

```ts
import { test, expect } from '@playwright/test'
import { fetchDeliveryBoard, fetchTranscript } from './helpers/api'
import {
  extractLabeledValue,
  kickoffDeliveryButton,
  kickoffTranscriptButton,
  uniqueRequirementTitle,
  waitForClarifyDialog,
} from './helpers/selectors'

test('real MVP clarify -> kickoff -> delivery flow produces transcript and board artifacts', async ({ page }, testInfo) => {
  test.setTimeout(10 * 60 * 1000)

  const requirementTitle = uniqueRequirementTitle()
  let meetingId = ''
  let projectId = ''

  await page.goto('/')

  await page.getByRole('button', { name: 'Create MVP Requirement' }).click()
  await page.getByLabel('Title').fill(requirementTitle)
  await page.getByLabel('Description').fill('Create a snake game MVP for web with single-player gameplay.')
  await page.getByRole('button', { name: 'Create Requirement' }).click()

  await expect(page.getByText(requirementTitle)).toBeVisible()
  await page.getByRole('button', { name: 'Clarify MVP' }).first().click()

  await waitForClarifyDialog(page)

  await page.getByPlaceholder(/Type your message/i).fill(
    'Build a snake MVP for web. Single player only. Keyboard controls. No leaderboard yet.',
  )
  await page.getByRole('button', { name: 'Send' }).click()

  await expect(page.getByText(/Goal:/)).toBeVisible()
  await expect(page.getByText(/Single player|keyboard|web/i)).toBeVisible({ timeout: 120000 })

  const kickoffButton = page.getByRole('button', { name: 'Start Kickoff Meeting' })
  await expect(kickoffButton).toBeEnabled({ timeout: 180000 })
  await kickoffButton.click()

  await expect(page.getByText(/Kickoff Running|Generating Delivery Plan|Kickoff Complete/)).toBeVisible()
  await expect(page.getByText('Project ID:')).toBeVisible({ timeout: 360000 })
  await expect(page.getByText('Meeting ID:')).toBeVisible()

  meetingId = await extractLabeledValue(page, 'Meeting ID')
  projectId = await extractLabeledValue(page, 'Project ID')

  await expect(kickoffTranscriptButton(page)).toBeVisible()
  await kickoffTranscriptButton(page).click()
  await expect(page.getByText(/moderator/i)).toBeVisible({ timeout: 120000 })

  const transcript = await fetchTranscript(meetingId)
  expect(transcript.events.length).toBeGreaterThan(0)
  expect(transcript.events.some((event) => event.agent_role === 'moderator')).toBeTruthy()
  expect(transcript.events.some((event) => event.agent_role && event.agent_role !== 'moderator')).toBeTruthy()

  await page.keyboard.press('Escape')
  await kickoffDeliveryButton(page).click()

  await expect(page.getByRole('heading', { name: 'Delivery Board' })).toBeVisible({ timeout: 120000 })

  const board = await fetchDeliveryBoard()
  const hasOpenGate = board.decision_gates.some((gate) => gate.status === 'open')
  const hasPreviewTask = board.tasks.some((task) => task.status === 'preview')
  const hasReadyTask = board.tasks.some((task) => task.status === 'ready')
  expect(hasOpenGate || hasPreviewTask || hasReadyTask).toBeTruthy()

  await testInfo.attach('e2e-identifiers', {
    body: JSON.stringify({ requirementTitle, meetingId, projectId }, null, 2),
    contentType: 'application/json',
  })
})
```

- [ ] **Step 2: Run the new test to capture the first failure**

Run:

```powershell
npm --prefix web run e2e -- kickoff-to-delivery.spec.ts
```

Expected:
- The spec starts
- At least one selector, label, or flow step fails and tells us what UI mismatch must be fixed

- [ ] **Step 3: Adjust selectors and flow to match the real UI exactly**

Make only the minimal changes needed to the spec after observing the real failure. Common acceptable adjustments:

- use the actual dialog input selector
- tighten the correct create-requirement dialog labels
- scope the `Clarify MVP` button to the new card
- use the actual kickoff result text if it differs slightly

Do not weaken the artifact assertions.

- [ ] **Step 4: Re-run the spec until the happy path passes**

Run:

```powershell
npm --prefix web run e2e -- kickoff-to-delivery.spec.ts
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git add web/e2e/kickoff-to-delivery.spec.ts
git commit -m "test: add real kickoff to delivery E2E spec"
```

## Task 5: Improve Failure Diagnostics

**Files:**
- Modify: `web/playwright.config.ts`
- Modify: `web/e2e/kickoff-to-delivery.spec.ts`

- [ ] **Step 1: Add HTML capture on failure in the spec**

Update the test with a `try/finally` or failure hook pattern so the page HTML is attached when the test fails:

```ts
if (testInfo.status !== testInfo.expectedStatus) {
  await testInfo.attach('page-html', {
    body: Buffer.from(await page.content()),
    contentType: 'text/html',
  })
}
```

- [ ] **Step 2: Keep the existing Playwright failure artifacts enabled**

Ensure `web/playwright.config.ts` still contains:

```ts
use: {
  baseURL,
  trace: 'retain-on-failure',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
}
```

- [ ] **Step 3: Re-run the happy-path spec**

Run:

```powershell
npm --prefix web run e2e -- kickoff-to-delivery.spec.ts
```

Expected:
- PASS
- No regression from the new attachment logic

- [ ] **Step 4: Commit**

```powershell
git add web/playwright.config.ts web/e2e/kickoff-to-delivery.spec.ts
git commit -m "test: improve E2E failure diagnostics"
```

## Task 6: Document How To Run The Real Browser Check

**Files:**
- Modify: `docs/frontend-mvp-cycle.md`

- [ ] **Step 1: Add a short E2E section to the doc**

Append a concise section like this:

```md
## Playwright E2E

You can replace manual browser clicking with the real Playwright check.

Start services manually first:

```powershell
uv run uvicorn studio.api.main:create_app --factory --reload
npm --prefix web run dev
```

Then run:

```powershell
npm --prefix web run e2e -- kickoff-to-delivery.spec.ts
```

Optional environment variables:

- `E2E_BASE_URL`
- `E2E_API_URL`
- `E2E_WORKSPACE`

The test drives the real browser flow and verifies transcript plus delivery artifacts through backend APIs.
```

- [ ] **Step 2: Verify the doc reads cleanly**

Run:

```powershell
Get-Content docs\\frontend-mvp-cycle.md | Select-Object -Last 40
```

Expected:
- The new section is present
- No formatting breakage

- [ ] **Step 3: Commit**

```powershell
git add docs/frontend-mvp-cycle.md
git commit -m "docs: add Playwright E2E run instructions"
```

## Task 7: Final Verification

**Files:**
- Verify only

- [ ] **Step 1: Run the frontend build**

Run:

```powershell
npm --prefix web run build
```

Expected:
- PASS

- [ ] **Step 2: Run the Playwright spec**

Run:

```powershell
npm --prefix web run e2e -- kickoff-to-delivery.spec.ts
```

Expected:
- PASS

- [ ] **Step 3: Summarize outputs for handoff**

Record:

- whether the spec passed
- the last generated requirement title
- the last discovered `meeting_id`
- the last discovered `project_id`
- where Playwright HTML report and traces are stored

- [ ] **Step 4: Commit any final plan-following fixes**

```powershell
git status --short
```

Expected:
- no unexpected files remain

## Plan Self-Review

### Spec Coverage

- Real browser flow: covered in Task 4
- Transcript verification: covered in Tasks 2 and 4
- Delivery verification: covered in Tasks 2 and 4
- Failure diagnostics: covered in Task 5
- Operator-run workflow docs: covered in Task 6

### Placeholder Scan

No `TODO`, `TBD`, or deferred implementation placeholders remain in the plan.

### Type Consistency

The helper and spec names are consistent:

- `fetchTranscript`
- `fetchDeliveryBoard`
- `uniqueRequirementTitle`
- `extractLabeledValue`

