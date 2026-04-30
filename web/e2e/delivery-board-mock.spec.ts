import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fetchDeliveryBoard } from './helpers/api'

const now = '2026-04-30T00:00:00+00:00'

function writeJson(root: string, collection: string, id: string, payload: unknown) {
  const dir = join(root, '.studio-data', collection)
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, `${id}.json`), JSON.stringify(payload, null, 2), 'utf-8')
}

function seedDeliveryBoard(workspace: string) {
  const requirementId = 'req_mock_delivery'
  const meetingId = 'meeting_mock_delivery'
  const projectId = 'proj_mock_delivery'
  const planId = 'plan_mock_delivery'
  const gateId = 'gate_mock_delivery'

  writeJson(workspace, 'delivery_plans', planId, {
    id: planId,
    meeting_id: meetingId,
    requirement_id: requirementId,
    project_id: projectId,
    status: 'awaiting_user_decision',
    task_ids: [
      'task_preview_art',
      'task_blocked_dev',
      'task_ready_qa',
      'task_done_design',
    ],
    decision_gate_id: gateId,
    decision_resolution_version: null,
    created_at: now,
    updated_at: now,
  })

  writeJson(workspace, 'kickoff_decision_gates', gateId, {
    id: gateId,
    plan_id: planId,
    meeting_id: meetingId,
    requirement_id: requirementId,
    project_id: projectId,
    status: 'open',
    resolution_version: 0,
    items: [
      {
        id: 'visual_style',
        question: 'Choose the UI style',
        context: 'The delivery plan needs a final style direction before implementation.',
        options: ['Pixel art', 'Minimal geometric'],
        resolution: null,
      },
    ],
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

  writeJson(workspace, 'delivery_tasks', 'task_preview_art', {
    ...baseTask,
    id: 'task_preview_art',
    title: 'Prepare visual direction',
    description: 'Create an art direction note after the style decision is made.',
    owner_agent: 'art',
    status: 'preview',
    depends_on_task_ids: [],
  })

  writeJson(workspace, 'delivery_tasks', 'task_blocked_dev', {
    ...baseTask,
    id: 'task_blocked_dev',
    title: 'Implement game shell',
    description: 'Use the visual direction and build the playable shell.',
    owner_agent: 'dev',
    status: 'blocked',
    depends_on_task_ids: ['task_preview_art'],
  })

  writeJson(workspace, 'delivery_tasks', 'task_ready_qa', {
    ...baseTask,
    id: 'task_ready_qa',
    title: 'Write smoke checklist',
    description: 'Prepare a lightweight verification checklist.',
    owner_agent: 'qa',
    status: 'ready',
    depends_on_task_ids: [],
  })

  writeJson(workspace, 'delivery_tasks', 'task_done_design', {
    ...baseTask,
    id: 'task_done_design',
    title: 'Draft GDD',
    description: 'Capture the core rules and delivery assumptions.',
    owner_agent: 'design',
    status: 'done',
    depends_on_task_ids: [],
    execution_result_id: 'result_task_done_design',
    output_artifact_ids: ['docs/GDD.md'],
  })

  writeJson(workspace, 'task_execution_results', 'result_task_done_design', {
    id: 'result_task_done_design',
    task_id: 'task_done_design',
    plan_id: planId,
    project_id: projectId,
    agent: 'design',
    session_id: 'sess_design_mock',
    summary: 'Design doc created',
    output_artifact_ids: ['docs/GDD.md'],
    changed_files: ['docs/GDD.md'],
    tests_or_checks: ['Reviewed core flow'],
    follow_up_notes: [],
    dependency_context_used: [],
    decision_context_used: [],
    context_warnings: [],
    created_at: now,
  })

  return { requirementId, meetingId, projectId, planId, gateId }
}

test('delivery board renders seeded plan, gate, dependencies, and artifacts', async ({ page }, testInfo) => {
  const workspace = `.e2e-workspaces/delivery-board-mock-${Date.now()}`
  const seeded = seedDeliveryBoard(join('..', workspace))
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
  await expect(page.getByText(`Filtered: ${seeded.requirementId}`)).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Kickoff Decision Needed (1)' })).toBeVisible()
  await expect(page.getByText('Choose the UI style')).toBeVisible()
  await expect(page.getByText('Pixel art')).toBeVisible()
  await expect(page.getByText('Minimal geometric')).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Preview (1)' })).toBeVisible()
  await expect(page.getByText('Prepare visual direction')).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Blocked (1)' })).toBeVisible()
  await expect(page.getByText('Implement game shell')).toBeVisible()
  await expect(page.getByText('1 dep')).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Ready (1)' })).toBeVisible()
  await expect(page.getByText('Write smoke checklist')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start Agent Work' })).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Done (1)' })).toBeVisible()
  await expect(page.getByText('Draft GDD')).toBeVisible()
  await expect(page.getByText('1 file changed')).toBeVisible()
  await expect(page.getByText('docs/GDD.md')).toBeVisible()

  const board = await fetchDeliveryBoard(seeded.requirementId, workspace)
  expect(board.plans).toHaveLength(1)
  expect(board.tasks).toHaveLength(4)
  expect(board.decision_gates).toHaveLength(1)

  await testInfo.attach('mock-delivery-board', {
    body: JSON.stringify({ workspace, ...seeded }, null, 2),
    contentType: 'application/json',
  })
})
