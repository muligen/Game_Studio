import { expect, test } from '@playwright/test'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fetchDeliveryBoard } from './helpers/api'

const now = '2026-04-30T00:00:00+00:00'

function writeJson(root: string, collection: string, id: string, payload: unknown) {
  const dir = join(root, '.studio-data', collection)
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, `${id}.json`), JSON.stringify(payload, null, 2), 'utf-8')
}

function seedExecutableDelivery(workspace: string) {
  const requirementId = 'req_context_delivery'
  const meetingId = 'meeting_context_delivery'
  const projectId = `proj_context_delivery_${Date.now()}`
  const planId = 'plan_context_delivery'
  const gateId = 'gate_context_delivery'
  mkdirSync(join(workspace, '.studio-data'), { recursive: true })
  writeFileSync(join(workspace, '.studio-data', 'e2e_stub_delivery_agents'), 'true', 'utf-8')

  writeJson(workspace, 'requirements', requirementId, {
    id: requirementId,
    title: 'Snake MVP with shared context',
    kind: 'product_mvp',
    type: 'requirement',
    priority: 'medium',
    status: 'approved',
    owner: 'design_agent',
    design_doc_id: null,
    balance_table_ids: [],
    bug_ids: [],
    notes: [],
    created_at: now,
  })

  writeJson(workspace, 'meetings', meetingId, {
    id: meetingId,
    requirement_id: requirementId,
    title: 'Snake Delivery Kickoff',
    agenda: ['Build a small Snake MVP'],
    attendees: ['art', 'dev'],
    opinions: [],
    consensus_points: ['Use browser delivery', 'Keep scope small'],
    conflict_points: [],
    supplementary: {},
    decisions: ['Use Canvas'],
    action_items: [],
    pending_user_decisions: ['Choose visual style'],
    status: 'completed',
  })

  for (const agent of ['art', 'dev']) {
    writeJson(workspace, 'project_agent_sessions', `${projectId}_${agent}`, {
      id: `${projectId}_${agent}`,
      project_id: projectId,
      requirement_id: requirementId,
      agent,
      session_id: `sess_${agent}_context`,
      status: 'active',
      created_at: now,
      last_used_at: now,
    })
  }

  writeJson(workspace, 'delivery_plans', planId, {
    id: planId,
    meeting_id: meetingId,
    requirement_id: requirementId,
    project_id: projectId,
    status: 'awaiting_user_decision',
    task_ids: ['task_context_art', 'task_context_dev'],
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
        context: 'The agents must use this resolved style during delivery.',
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
    meeting_snapshot: null,
    decision_resolution_version: null,
    created_at: now,
    updated_at: now,
  }

  writeJson(workspace, 'delivery_tasks', 'task_context_art', {
    ...baseTask,
    id: 'task_context_art',
    title: 'Create pixel art guide',
    description: 'Write an art guide for the confirmed visual style.',
    owner_agent: 'art',
    status: 'preview',
    depends_on_task_ids: [],
    acceptance_criteria: ['Art guide exists'],
  })

  writeJson(workspace, 'delivery_tasks', 'task_context_dev', {
    ...baseTask,
    id: 'task_context_dev',
    title: 'Implement UI from art guide',
    description: 'Use the upstream art guide and confirmed style decision.',
    owner_agent: 'dev',
    status: 'preview',
    depends_on_task_ids: ['task_context_art'],
    acceptance_criteria: ['Dev receives art context'],
  })

  return { requirementId, projectId, planId }
}

async function waitForDoneTasks(requirementId: string, workspace: string) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const board = await fetchDeliveryBoard(requirementId, workspace)
    if (board.tasks.length === 2 && board.tasks.every((task) => task.status === 'done')) {
      return board
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  throw new Error('Timed out waiting for seeded delivery tasks to complete')
}

test('delivery runner gives downstream agents resolved decisions and dependency artifacts', async ({ page }, testInfo) => {
  const workspace = `.e2e-workspaces/delivery-agent-context-${Date.now()}`
  const workspaceOnDisk = join('..', workspace)
  const seeded = seedExecutableDelivery(workspaceOnDisk)
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
  await expect(page.getByRole('heading', { name: 'Kickoff Decision Needed (1)' })).toBeVisible()
  await page.getByRole('button', { name: 'Resolve Decisions' }).click()

  const dialog = page.getByRole('dialog', { name: 'Resolve Kickoff Decisions' })
  await expect(dialog).toBeVisible()
  await dialog.locator('select').selectOption('Pixel art')
  await dialog.getByRole('button', { name: 'Resolve' }).click()
  await expect(dialog).not.toBeVisible()

  const board = await waitForDoneTasks(seeded.requirementId, workspace)
  expect(board.tasks.map((task) => task.status)).toEqual(['done', 'done'])

  const projectRoot = join(workspaceOnDisk, '..', 'GS_projects', seeded.projectId)
  const artContextPath = join(projectRoot, 'debug', 'art-context.json')
  const devContextPath = join(projectRoot, 'debug', 'dev-context.json')
  expect(existsSync(artContextPath)).toBeTruthy()
  expect(existsSync(devContextPath)).toBeTruthy()

  const artContext = JSON.parse(readFileSync(artContextPath, 'utf-8'))
  const devContext = JSON.parse(readFileSync(devContextPath, 'utf-8'))
  expect(artContext.resolved_decisions).toEqual([
    {
      id: 'visual_style',
      question: 'Choose the UI style',
      resolution: 'Pixel art',
    },
  ])
  expect(devContext.resolved_decisions[0].resolution).toBe('Pixel art')
  expect(devContext.dependency_results[0].task_id).toBe('task_context_art')
  expect(devContext.dependency_artifact_files).toContain('art/ART_GUIDE.md')
  expect(devContext.dependency_artifact_excerpts[0].excerpt).toContain('Pixel art')

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Done (2)' })).toBeVisible({ timeout: 30000 })
  await expect(page.getByText('art/ART_GUIDE.md')).toBeVisible()
  await expect(page.getByText('game/index.html')).toBeVisible()

  await testInfo.attach('delivery-agent-context', {
    body: JSON.stringify({ workspace, ...seeded, artContext, devContext }, null, 2),
    contentType: 'application/json',
  })
})
