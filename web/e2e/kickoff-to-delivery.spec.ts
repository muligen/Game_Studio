import { expect, type Locator, test } from '@playwright/test'
import { fetchDeliveryBoard, fetchTranscript } from './helpers/api'
import {
  extractLabeledValue,
  kickoffDeliveryButton,
  kickoffTranscriptButton,
  uniqueRequirementTitle,
  waitForClarifyDialog,
} from './helpers/selectors'

const clarificationAnswers = [
  'Build a browser-based Snake MVP using React and TypeScript. It is single-player, keyboard controlled, and targets modern desktop Chrome and Edge. Use classic Snake rules: 20x20 grid, moderate starting speed, no wrap-around, eating food grows the snake and adds 1 point, wall or self collision ends the game, endless high-score chase with no win condition, and a simple retro arcade visual style. Acceptance criteria: arrow keys move the snake, food appears on the grid, score increments on food, snake grows after eating, game over appears on collision, restart resets score and board state, and the game works without backend services. Main risks are scope creep beyond classic Snake and unclear polish expectations. For this kickoff validation, use design as the only meeting attendee.',
  'Confirm the MVP scope stays classic Snake only: no leaderboard, no mobile touch controls, no backend persistence, no levels, and no multiplayer. The deliverable should be a playable web game loop with clear restart and game-over behavior.',
  'Use design as the only meeting attendee. Design should focus on retro visual clarity, readable score/game-over states, and keeping the MVP scope small.',
]

async function waitForClarificationAttempt(
  dialog: Locator,
  input: Locator,
  kickoffButton: Locator,
  timeoutMs = 90000,
): Promise<'accepted' | 'ready' | 'failed'> {
  const deadline = Date.now() + timeoutMs
  const error = dialog.getByText(/Clarification agent failed/)

  while (Date.now() < deadline) {
    if (await kickoffButton.isEnabled()) {
      return 'ready'
    }

    const value = await input.inputValue().catch(() => '')
    const disabled = await input.isDisabled().catch(() => false)
    if (!value && !disabled) {
      return 'accepted'
    }

    if ((await error.isVisible().catch(() => false)) && !disabled) {
      return 'failed'
    }

    await dialog.page().waitForTimeout(1000)
  }

  return 'failed'
}

async function hasSuggestedDesignAttendee(dialog: Locator): Promise<boolean> {
  const suggestedAttendees = dialog.locator('div').filter({ hasText: 'Suggested Attendees' }).first()
  return suggestedAttendees.getByText('design', { exact: true }).isVisible().catch(() => false)
}

test('real MVP clarify -> kickoff -> delivery flow produces transcript and board artifacts', async ({ page }, testInfo) => {
  test.setTimeout(10 * 60 * 1000)

  const workspace = `.e2e-workspaces/kickoff-to-delivery-${Date.now()}`
  const uiApiBaseUrl = process.env.E2E_UI_API_URL
  let requirementTitle = uniqueRequirementTitle()
  let meetingId = ''
  let projectId = ''
  let requirementId = ''

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    if (uiApiBaseUrl) {
      const target = new URL(uiApiBaseUrl)
      url.protocol = target.protocol
      url.host = target.host
    }
    if (url.searchParams.has('workspace')) {
      url.searchParams.set('workspace', workspace)
      await route.continue({ url: url.toString() })
      return
    }

    await route.continue()
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Current Product Workbench' })).toBeVisible()

  const createMvpButton = page.getByRole('button', { name: 'Create MVP Requirement' })
  const continueClarifyingButton = page.getByRole('button', { name: 'Continue Clarifying MVP' })

  if (await createMvpButton.isVisible().catch(() => false)) {
    await createMvpButton.click()

    const createDialog = page.getByRole('dialog')
    await expect(createDialog.getByText('Create MVP Requirement')).toBeVisible()
    await createDialog.getByPlaceholder('Describe the product you want to build.').fill(requirementTitle)
    await createDialog.getByRole('button', { name: 'Create' }).click()

    await expect(page.getByRole('heading', { name: requirementTitle, exact: true })).toBeVisible()
  } else {
    requirementTitle = 'existing-mvp'
  }

  await expect(continueClarifyingButton).toBeVisible()
  await continueClarifyingButton.click()

  await waitForClarifyDialog(page)

  const clarificationDialog = page.getByRole('dialog')
  const kickoffButton = clarificationDialog.getByRole('button', { name: 'Start Kickoff Meeting' })
  const messageInput = clarificationDialog.getByPlaceholder('Describe the MVP feature...')
  const sendButton = clarificationDialog.getByRole('button', { name: 'Send' })

  for (const answer of clarificationAnswers) {
    if ((await kickoffButton.isEnabled()) && (await hasSuggestedDesignAttendee(clarificationDialog))) {
      break
    }

    for (let attempt = 0; attempt < 2; attempt += 1) {
      await messageInput.fill(answer)
      await sendButton.click()
      const result = await waitForClarificationAttempt(clarificationDialog, messageInput, kickoffButton)
      if (result !== 'failed' && (await hasSuggestedDesignAttendee(clarificationDialog))) {
        break
      }
    }
  }

  await expect(kickoffButton).toBeEnabled({ timeout: 180000 })
  await expect(
    clarificationDialog.locator('div').filter({ hasText: 'Suggested Attendees' }).first().getByText('design', {
      exact: true,
    }),
  ).toBeVisible()
  await kickoffButton.click()

  await expect(clarificationDialog.getByText(/Kickoff Running|Generating Delivery Plan|Kickoff Complete/)).toBeVisible()
  await expect(clarificationDialog.getByText(/Kickoff Complete/)).toBeVisible({ timeout: 360000 })

  meetingId = await extractLabeledValue(clarificationDialog, 'Meeting ID')
  projectId = await extractLabeledValue(clarificationDialog, 'Project ID')

  await expect(kickoffTranscriptButton(page)).toBeVisible()
  await kickoffTranscriptButton(page).click()

  const transcriptDialog = page.getByRole('dialog', { name: 'Meeting Transcript' })
  await expect(transcriptDialog.getByRole('heading', { name: 'Meeting Transcript' })).toBeVisible({
    timeout: 120000,
  })

  const transcript = await fetchTranscript(meetingId, workspace)
  requirementId = transcript.requirement_id
  expect(transcript.meeting_id).toBe(meetingId)
  expect(transcript.project_id).toBe(projectId)
  expect(transcript.events.length).toBeGreaterThan(0)
  expect(transcript.events.some((event) => event.agent_role === 'moderator')).toBeTruthy()
  expect(
    transcript.events.some((event) =>
      ['design', 'dev', 'qa', 'art', 'quality', 'reviewer'].includes(event.agent_role),
    ),
  ).toBeTruthy()
  expect(
    transcript.events.some((event) => typeof event.message === 'string' && event.message.trim().length > 0),
  ).toBeTruthy()

  await transcriptDialog.getByRole('button', { name: 'Close' }).click()
  await expect(transcriptDialog).not.toBeVisible()

  await kickoffDeliveryButton(page).click()
  await expect(page.getByRole('heading', { name: 'Delivery Board' })).toBeVisible({ timeout: 120000 })

  const board = await fetchDeliveryBoard(requirementId, workspace)
  const relatedPlans = board.plans.filter(
    (plan) =>
      plan.meeting_id === meetingId &&
      plan.project_id === projectId &&
      plan.requirement_id === requirementId,
  )
  const relatedTasks = board.tasks.filter(
    (task) =>
      task.meeting_id === meetingId &&
      task.project_id === projectId &&
      task.requirement_id === requirementId,
  )
  const relatedGates = board.decision_gates.filter(
    (gate) =>
      gate.meeting_id === meetingId &&
      gate.project_id === projectId &&
      gate.requirement_id === requirementId,
  )

  expect(relatedPlans.length).toBeGreaterThan(0)
  expect(relatedTasks.length + relatedGates.length).toBeGreaterThan(0)
  expect(
    relatedTasks.some((task) => ['preview', 'blocked', 'ready', 'in_progress', 'review', 'done'].includes(task.status)) ||
      relatedGates.some((gate) => ['open', 'resolved'].includes(gate.status)),
  ).toBeTruthy()

  await testInfo.attach('e2e-identifiers', {
    body: JSON.stringify({ workspace, requirementTitle, requirementId, meetingId, projectId }, null, 2),
    contentType: 'application/json',
  })
})
