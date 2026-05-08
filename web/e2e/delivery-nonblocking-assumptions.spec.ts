import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fetchDeliveryBoard } from './helpers/api'

const now = '2026-05-08T00:00:00+00:00'

function writeJson(root: string, collection: string, id: string, payload: unknown) {
  const dir = join(root, '.studio-data', collection)
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, `${id}.json`), JSON.stringify(payload, null, 2), 'utf-8')
}

function seedNonblockingBoard(workspace: string) {
  const requirementId = 'req_noblock_delivery'
  const meetingId = 'meeting_noblock_delivery'
  const projectId = 'proj_noblock_delivery'
  const planId = 'plan_noblock_delivery'

  writeJson(workspace, 'delivery_plans', planId, {
    id: planId,
    meeting_id: meetingId,
    requirement_id: requirementId,
    project_id: projectId,
    status: 'active',
    task_ids: [
      'task_ready_dev',
      'task_ready_qa',
    ],
    decision_gate_id: null,
    decision_resolution_version: null,
    created_at: now,
    updated_at: now,
  })

  const baseTask = {
    plan_id: planId,
    meeting_id: meetingId,
    requirement_id: requirementId,
    project_id: projectId,
    execution_result_id: null,
    output_artifact_ids: [],
    acceptance_criteria: ['Criterion recorded'],
    meeting_snapshot: null,
    decision_resolution_version: null,
    created_at: now,
    updated_at: now,
  }

  writeJson(workspace, 'delivery_tasks', 'task_ready_dev', {
    ...baseTask,
    id: 'task_ready_dev',
    title: 'Implement core game loop',
    description: 'Build the main game loop with default pixel-art style.',
    owner_agent: 'dev',
    status: 'ready',
    depends_on_task_ids: [],
  })

  writeJson(workspace, 'delivery_tasks', 'task_ready_qa', {
    ...baseTask,
    id: 'task_ready_qa',
    title: 'Write smoke tests',
    description: 'Prepare automated smoke test suite.',
    owner_agent: 'qa',
    status: 'ready',
    depends_on_task_ids: [],
  })

  writeJson(workspace, 'project_assumptions', 'assump_style', {
    id: 'assump_style',
    requirement_id: requirementId,
    project_id: projectId,
    source: 'planner',
    category: 'art',
    decision: 'Use pixel-art style as default visual direction',
    rationale: 'No explicit art direction provided; pixel-art is the most common indie starting point.',
    impact: 'Low — easily re-skinnable later',
    owner_agent: 'design',
    change_policy: 'next_iteration',
    created_at: now,
  })

  writeJson(workspace, 'project_assumptions', 'assump_scope', {
    id: 'assump_scope',
    requirement_id: requirementId,
    project_id: projectId,
    source: 'planner',
    category: 'scope',
    decision: 'Single-player only for initial prototype',
    rationale: 'Multiplayer adds significant complexity; no network requirements mentioned.',
    impact: 'Medium — architecture decision affects extensibility',
    owner_agent: 'dev',
    change_policy: 'next_iteration',
    created_at: now,
  })

  writeJson(workspace, 'needs_attention_items', 'na_audio', {
    id: 'na_audio',
    requirement_id: requirementId,
    project_id: projectId,
    plan_id: planId,
    blocker: 'Audio engine license unclear — commercial use of SoundEngine Pro requires paid license',
    evidence: [
      'Meeting notes reference SoundEngine Pro for audio',
      'License terms not confirmed with legal',
    ],
    recommended_action: 'Confirm audio engine license before starting audio tasks',
    affected_task_ids: [],
    resumable: true,
    status: 'open',
    created_at: now,
  })

  return { requirementId, meetingId, projectId, planId }
}

test('delivery board renders non-blocking plan with assumptions and needs-attention', async ({ page }, testInfo) => {
  const workspace = `.e2e-workspaces/delivery-noblock-${Date.now()}`
  const seeded = seedNonblockingBoard(join('..', workspace))
  const uiApiBaseUrl = process.env.E2E_UI_API_URL

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    if (uiApiBaseUrl) {
      const target = new URL(uiApiBaseUrl)
      url.protocol = target.protocol
      url.host = target.host
    }
    if (url.searchParams.has('workspace')) {
      url.searchParams.set('workspace', workspace)
    }
    await route.continue({ url: url.toString() })
  })

  await page.goto(`/delivery?requirement_id=${seeded.requirementId}`)

  await expect(page.getByRole('heading', { name: 'Delivery Board' })).toBeVisible()

  // No decision gate column should appear
  await expect(page.getByRole('heading', { name: 'Kickoff Decision Needed' })).not.toBeVisible()

  // Assumptions panel should show decisions
  await expect(page.getByText('Assumptions & Decisions')).toBeVisible()
  await expect(page.getByText('Use pixel-art style as default visual direction')).toBeVisible()
  await expect(page.getByText('Single-player only for initial prototype')).toBeVisible()

  // Needs Attention panel should show blocker
  await expect(page.getByText('Needs Attention')).toBeVisible()
  await expect(page.getByText('Audio engine license unclear')).toBeVisible()
  await expect(page.getByText('Confirm audio engine license')).toBeVisible()

  // Task columns render correctly without gate column
  await expect(page.getByRole('heading', { name: 'Ready (2)' })).toBeVisible()
  await expect(page.getByText('Implement core game loop')).toBeVisible()
  await expect(page.getByText('Write smoke tests')).toBeVisible()

  // Verify API returns assumptions and needs_attention_items
  const board = await fetchDeliveryBoard(seeded.requirementId, workspace)
  expect(board.plans).toHaveLength(1)
  expect(board.plans[0].status).toBe('active')
  expect(board.tasks).toHaveLength(2)
  expect(board.decision_gates).toHaveLength(0)

  await testInfo.attach('nonblocking-delivery-board', {
    body: JSON.stringify({ workspace, ...seeded }, null, 2),
    contentType: 'application/json',
  })
})
