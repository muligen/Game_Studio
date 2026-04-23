# Single Product Workbench Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic requirements Kanban board with a single-product workbench that distinguishes Product MVP from Change Requests, uses lifecycle columns, and provides mode-aware clarification.

**Architecture:** A frontend-only refactor using a derived state helper (`deriveProductWorkbenchState`) that computes product baseline status and requirement kinds from the existing requirements list. The page splits into three components: a status header, a lifecycle board, and mode-aware clarification. No backend changes needed in Phase 1.

**Tech Stack:** React 18, TypeScript, TanStack Query, shadcn/ui, Tailwind CSS

---

## Scope Check

This spec is frontend-focused with a single cohesive concern: reframing the requirements board as a product workbench. It touches multiple files but they are all part of one UI transformation. Kept as one plan.

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `web/src/lib/product-workbench.ts` | Create | Types, derived state helper, lifecycle column mapping |
| `web/src/components/board/ProductWorkbenchHeader.tsx` | Create | Product status card with dynamic copy and action button |
| `web/src/components/board/ProductLifecycleBoard.tsx` | Create | Lifecycle columns (8 columns mapped from backend statuses) |
| `web/src/components/board/RequirementCard.tsx` | Modify | Add kind badge, next action label, lifecycle badge |
| `web/src/components/common/CreateRequirementDialog.tsx` | Modify | Mode-aware title/helper text based on baseline state |
| `web/src/components/common/RequirementClarificationDialog.tsx` | Modify | Mode-aware title, goal text, and preview sections |
| `web/src/pages/RequirementsBoard.tsx` | Modify | Replace with workbench layout using new components |
| `web/src/App.tsx` | Modify | Update nav label from "Requirements" to "Workbench" |

---

### Task 1: Product Workbench State Helper

**Files:**
- Create: `web/src/lib/product-workbench.ts`

This is the foundation — all components depend on these types and the derived state function.

- [ ] **Step 1: Create the state helper module**

```typescript
// web/src/lib/product-workbench.ts

import type { RequirementCard } from './api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RequirementKind = 'product_mvp' | 'change_request'
export type BaselineStatus = 'not_started' | 'defining_mvp' | 'active'

export interface ProductWorkbenchState {
  baselineStatus: BaselineStatus
  mvpRequirement: RequirementCard | null
  changeRequests: RequirementCard[]
  requirementKinds: Map<string, RequirementKind>
}

// ---------------------------------------------------------------------------
// Lifecycle column mapping
// ---------------------------------------------------------------------------

export interface LifecycleColumn {
  key: string
  title: string
  statuses: string[]
}

export const LIFECYCLE_COLUMNS: LifecycleColumn[] = [
  { key: 'product_setup', title: 'Product Setup', statuses: ['draft'] },
  { key: 'clarifying', title: 'Clarifying', statuses: ['designing'] },
  { key: 'ready_for_meeting', title: 'Ready for Meeting', statuses: ['pending_user_review'] },
  { key: 'decision_needed', title: 'Decision Needed', statuses: [] },
  { key: 'ready_for_delivery', title: 'Ready for Delivery', statuses: ['approved'] },
  { key: 'in_progress', title: 'In Progress', statuses: ['implementing', 'self_test_passed', 'testing'] },
  { key: 'review_acceptance', title: 'Review / Acceptance', statuses: ['pending_user_acceptance', 'quality_check'] },
  { key: 'done', title: 'Done', statuses: ['done'] },
]

// ---------------------------------------------------------------------------
// Next action labels
// ---------------------------------------------------------------------------

export function getNextAction(
  kind: RequirementKind,
  status: string,
  hasDesignDoc: boolean,
): string {
  if (status === 'draft') return kind === 'product_mvp' ? 'Clarify MVP' : 'Clarify Change'
  if (status === 'designing') return kind === 'product_mvp' ? 'Clarify MVP' : 'Clarify Change'
  if (status === 'pending_user_review') return 'Start Kickoff'
  if (status === 'approved') return 'Start Delivery'
  if (status === 'pending_user_acceptance' || status === 'quality_check') return 'Review'
  if (status === 'implementing' || status === 'testing' || status === 'self_test_passed')
    return 'In Progress'
  if (status === 'done') return 'Done'
  return status.replace(/_/g, ' ')
}

// ---------------------------------------------------------------------------
// Derived state
// ---------------------------------------------------------------------------

export function deriveProductWorkbenchState(
  requirements: RequirementCard[],
): ProductWorkbenchState {
  if (requirements.length === 0) {
    return {
      baselineStatus: 'not_started',
      mvpRequirement: null,
      changeRequests: [],
      requirementKinds: new Map(),
    }
  }

  const sorted = [...requirements].sort((a, b) => {
    const aTime = a.created_at || ''
    const bTime = b.created_at || ''
    return aTime.localeCompare(bTime)
  })

  const mvpRequirement = sorted[0]
  const mvpIsDone = mvpRequirement.status === 'done'
  const baselineStatus: BaselineStatus = mvpIsDone ? 'active' : 'defining_mvp'

  const kinds = new Map<string, RequirementKind>()
  kinds.set(mvpRequirement.id, mvpIsDone ? 'product_mvp' : 'product_mvp')

  const changeRequests: RequirementCard[] = []
  for (let i = 1; i < sorted.length; i++) {
    const req = sorted[i]
    if (baselineStatus === 'active') {
      kinds.set(req.id, 'change_request')
      changeRequests.push(req)
    } else {
      // Before baseline is active, all are treated as part of MVP definition
      kinds.set(req.id, 'product_mvp')
    }
  }

  return {
    baselineStatus,
    mvpRequirement,
    changeRequests,
    requirementKinds: kinds,
  }
}

// ---------------------------------------------------------------------------
// Column assignment
// ---------------------------------------------------------------------------

export function getLifecycleColumnKey(status: string): string {
  for (const col of LIFECYCLE_COLUMNS) {
    if (col.statuses.includes(status)) return col.key
  }
  return 'product_setup'
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: No errors (the file is self-contained with no new dependencies)

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/product-workbench.ts
git commit -m "feat: add product workbench state helper with lifecycle mapping"
```

---

### Task 2: Product Workbench Header Component

**Files:**
- Create: `web/src/components/board/ProductWorkbenchHeader.tsx`

- [ ] **Step 1: Create the header component**

```tsx
// web/src/components/board/ProductWorkbenchHeader.tsx
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import type { BaselineStatus } from '@/lib/product-workbench'

interface ProductWorkbenchHeaderProps {
  baselineStatus: BaselineStatus
  onCreateRequirement: () => void
  onContinueClarifying?: () => void
  mvpRequirementId?: string | null
  latestMeetingId?: string | null
}

const STATUS_CONFIG: Record<BaselineStatus, {
  title: string
  description: string
  actionLabel: string
  actionKind: 'create' | 'clarify'
  icon: string
  cardClass: string
}> = {
  not_started: {
    title: 'No product baseline yet',
    description: 'Create and clarify the first requirement to define the MVP.',
    actionLabel: 'Create MVP Requirement',
    actionKind: 'create',
    icon: '\uD83D\uDEE0\uFE0F',
    cardClass: 'bg-gradient-to-r from-gray-50 to-gray-100 border-gray-200',
  },
  defining_mvp: {
    title: 'MVP definition in progress',
    description: 'Clarify the product goal, MVP scope, constraints, and acceptance criteria before kickoff.',
    actionLabel: 'Continue Clarifying MVP',
    actionKind: 'clarify',
    icon: '\uD83D\uDCDD',
    cardClass: 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200',
  },
  active: {
    title: 'Product baseline active',
    description: 'New requirements are treated as change requests against the current product.',
    actionLabel: 'Add Change Request',
    actionKind: 'create',
    icon: '\u2705',
    cardClass: 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200',
  },
}

export function ProductWorkbenchHeader({
  baselineStatus,
  onCreateRequirement,
  onContinueClarifying,
  mvpRequirementId,
  latestMeetingId,
}: ProductWorkbenchHeaderProps) {
  const config = STATUS_CONFIG[baselineStatus]

  const handleAction = () => {
    if (config.actionKind === 'clarify' && onContinueClarifying) {
      onContinueClarifying()
    } else {
      onCreateRequirement()
    }
  }

  return (
    <Card className={`p-6 border ${config.cardClass}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-2xl">{config.icon}</span>
            <h2 className="text-xl font-semibold text-gray-900">{config.title}</h2>
          </div>
          <p className="text-gray-600 text-sm mb-3">{config.description}</p>

          {baselineStatus === 'active' && (
            <div className="flex gap-4 text-xs text-muted-foreground">
              {mvpRequirementId && (
                <span>MVP: {mvpRequirementId}</span>
              )}
              {latestMeetingId && (
                <span>Latest meeting: {latestMeetingId}</span>
              )}
            </div>
          )}

          {baselineStatus === 'active' && !latestMeetingId && (
            <div className="mt-2 text-xs text-muted-foreground italic">
              The product baseline will appear here after the MVP kickoff meeting.
            </div>
          )}
        </div>

        <Button onClick={handleAction} className="ml-4">
          {config.actionLabel}
        </Button>
      </div>
    </Card>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/board/ProductWorkbenchHeader.tsx
git commit -m "feat: add ProductWorkbenchHeader with baseline status display"
```

---

### Task 3: Product Lifecycle Board Component

**Files:**
- Create: `web/src/components/board/ProductLifecycleBoard.tsx`

- [ ] **Step 1: Create the lifecycle board**

This replaces `KanbanBoard` with lifecycle-column-based grouping.

```tsx
// web/src/components/board/ProductLifecycleBoard.tsx
import { RequirementCard } from './RequirementCard'
import {
  LIFECYCLE_COLUMNS,
  getLifecycleColumnKey,
  type RequirementKind,
} from '@/lib/product-workbench'

interface Requirement {
  id: string
  title: string
  status?: string
  priority?: string
  design_doc_id?: string | null
}

interface ProductLifecycleBoardProps {
  requirements: Requirement[]
  onCardClick: (id: string) => void
  workspace: string
  onClarify?: (id: string, title: string) => void
  requirementKinds: Map<string, RequirementKind>
}

export function ProductLifecycleBoard({
  requirements,
  onCardClick,
  workspace,
  onClarify,
  requirementKinds,
}: ProductLifecycleBoardProps) {
  const grouped = LIFECYCLE_COLUMNS.map((col) => ({
    ...col,
    cards: requirements.filter((req) => getLifecycleColumnKey(req.status || 'draft') === col.key),
  }))

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {grouped.map((col) => (
        <div key={col.key} className="flex-shrink-0 w-80">
          <div className="bg-gray-50 rounded-t-lg px-3 py-2 border-b">
            <h3 className="font-semibold text-sm uppercase text-gray-600">
              {col.title} ({col.cards.length})
            </h3>
          </div>
          <div className="space-y-3 pt-3">
            {col.cards.length === 0 ? (
              <p className="text-xs text-gray-400 px-3 italic">No items</p>
            ) : (
              col.cards.map((req) => (
                <RequirementCard
                  key={req.id}
                  id={req.id}
                  title={req.title}
                  status={req.status}
                  priority={req.priority}
                  design_doc_id={req.design_doc_id}
                  workspace={workspace}
                  kind={requirementKinds.get(req.id) || 'change_request'}
                  onClick={() => onCardClick(req.id)}
                  onClarify={onClarify ? () => onClarify(req.id, req.title) : undefined}
                />
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: Errors because `RequirementCard` doesn't have `kind` prop yet — that's expected, fixed in Task 4

- [ ] **Step 3: Commit**

```bash
git add web/src/components/board/ProductLifecycleBoard.tsx
git commit -m "feat: add ProductLifecycleBoard with 8 lifecycle columns"
```

---

### Task 4: Update RequirementCard with Kind Badge and Next Action

**Files:**
- Modify: `web/src/components/board/RequirementCard.tsx`

- [ ] **Step 1: Update RequirementCard**

Replace the entire file. Key changes:
- Add `kind` prop for MVP vs Change Request badge
- Add lifecycle-style next action label
- Keep existing TransitionMenu and status display

```tsx
// web/src/components/board/RequirementCard.tsx
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { TransitionMenu } from '@/components/common/TransitionMenu'
import { getRequirementTransitions } from '@/lib/transitions'
import { type RequirementKind, getNextAction } from '@/lib/product-workbench'

interface RequirementCardProps {
  id: string
  title: string
  status?: string
  priority?: string
  design_doc_id?: string | null
  workspace: string
  kind: RequirementKind
  onClick: () => void
  onClarify?: () => void
}

const KIND_CONFIG: Record<RequirementKind, { label: string; className: string }> = {
  product_mvp: { label: 'Product MVP', className: 'bg-indigo-100 text-indigo-800' },
  change_request: { label: 'Change Request', className: 'bg-amber-100 text-amber-800' },
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  designing: 'bg-blue-100 text-blue-800',
  pending_user_review: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  implementing: 'bg-purple-100 text-purple-800',
  testing: 'bg-orange-100 text-orange-800',
  done: 'bg-emerald-100 text-emerald-800',
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-gray-200',
  medium: 'bg-yellow-200',
  high: 'bg-red-200',
}

export function RequirementCard({
  id,
  title,
  status,
  priority,
  design_doc_id,
  workspace,
  kind,
  onClick,
  onClarify,
}: RequirementCardProps) {
  const statusValue = status || 'draft'
  const priorityValue = priority || 'medium'
  const kindConfig = KIND_CONFIG[kind]
  const nextAction = getNextAction(kind, statusValue, !!design_doc_id)

  return (
    <Card
      className="p-4 cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <div className="flex justify-between items-start mb-2">
        <Badge className={kindConfig.className}>{kindConfig.label}</Badge>
        <Badge className={PRIORITY_COLORS[priorityValue]}>{priorityValue}</Badge>
      </div>
      <h3 className="font-medium mb-2">{title}</h3>
      <div className="flex items-center justify-between mt-2">
        <span className="text-xs font-medium text-blue-600">{nextAction}</span>
        <TransitionMenu
          entityType="requirement"
          id={id}
          currentStatus={statusValue}
          workspace={workspace}
          allStatuses={getRequirementTransitions(statusValue)}
          designDocId={design_doc_id}
        />
      </div>
      {design_doc_id && (
        <a
          href={`/design-docs/${design_doc_id}`}
          className="text-xs text-blue-600 hover:underline mt-2 block"
          onClick={(e) => e.stopPropagation()}
        >
          View Design
        </a>
      )}
      {['draft', 'designing'].includes(statusValue) && onClarify && (
        <button
          className="text-xs text-blue-600 hover:underline mt-1 block"
          onClick={(e) => { e.stopPropagation(); onClarify() }}
        >
          Clarify
        </button>
      )}
    </Card>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: `RequirementsBoard.tsx` may error because it still uses `KanbanBoard` — that's fine, fixed in Task 7

- [ ] **Step 3: Commit**

```bash
git add web/src/components/board/RequirementCard.tsx
git commit -m "feat: add kind badge and next action label to RequirementCard"
```

---

### Task 5: Mode-Aware Create Requirement Dialog

**Files:**
- Modify: `web/src/components/common/CreateRequirementDialog.tsx`

- [ ] **Step 1: Update the creation dialog**

Add `baselineStatus` prop. Change title, button label, and placeholder based on whether we're creating MVP or a change request.

```tsx
// web/src/components/common/CreateRequirementDialog.tsx
import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { requirementsApi } from '@/lib/api'
import type { BaselineStatus } from '@/lib/product-workbench'

interface CreateRequirementDialogProps {
  workspace: string
  baselineStatus: BaselineStatus
}

const PRIORITIES = ['low', 'medium', 'high'] as const

const MODE_CONFIG: Record<BaselineStatus, {
  buttonLabel: string
  dialogTitle: string
  placeholder: string
}> = {
  not_started: {
    buttonLabel: 'Create MVP Requirement',
    dialogTitle: 'Create MVP Requirement',
    placeholder: 'Describe the product you want to build.',
  },
  defining_mvp: {
    buttonLabel: 'Create MVP Requirement',
    dialogTitle: 'Create MVP Requirement',
    placeholder: 'Describe the product you want to build.',
  },
  active: {
    buttonLabel: 'Add Change Request',
    dialogTitle: 'Add Change Request',
    placeholder: 'Describe what you want to add or change.',
  },
}

export function CreateRequirementDialog({ workspace, baselineStatus }: CreateRequirementDialogProps) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<'low' | 'medium' | 'high'>('medium')
  const queryClient = useQueryClient()
  const config = MODE_CONFIG[baselineStatus]

  const createMutation = useMutation({
    mutationFn: () => requirementsApi.create(workspace, title, priority),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements'] })
      setOpen(false)
      setTitle('')
      setPriority('medium')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    createMutation.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>{config.buttonLabel}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{config.dialogTitle}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={config.placeholder}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Priority</label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as 'low' | 'medium' | 'high')}
              className="w-full h-10 rounded-md border border-gray-300 px-3 text-sm"
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </div>
          {createMutation.error && (
            <p className="text-sm text-red-600">
              Error: {String(createMutation.error)}
            </p>
          )}
          <div className="flex justify-end gap-3">
            <DialogClose asChild>
              <Button type="button" variant="outline">Cancel</Button>
            </DialogClose>
            <Button type="submit" disabled={!title.trim() || createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: Errors in `RequirementsBoard.tsx` due to changed props — fixed in Task 7

- [ ] **Step 3: Commit**

```bash
git add web/src/components/common/CreateRequirementDialog.tsx
git commit -m "feat: mode-aware create dialog (MVP vs Change Request)"
```

---

### Task 6: Mode-Aware Clarification Dialog

**Files:**
- Modify: `web/src/components/common/RequirementClarificationDialog.tsx`

- [ ] **Step 1: Update the clarification dialog**

Add `requirementKind` prop. Change dialog title, goal text, and context preview sections based on kind.

```tsx
// web/src/components/common/RequirementClarificationDialog.tsx
import { useState, useRef, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { useMutation } from '@tanstack/react-query'
import { clarificationsApi, type ClarificationSession, type MeetingContextDraft } from '@/lib/api'
import type { RequirementKind } from '@/lib/product-workbench'

interface Props {
  workspace: string
  requirementId: string
  requirementTitle: string
  requirementKind: RequirementKind
  open: boolean
  onOpenChange: (open: boolean) => void
}

const MODE_CONFIG: Record<RequirementKind, {
  dialogTitle: string
  goalText: string
  previewTitle: string
  fields: { key: keyof MeetingContextDraft; label: string }[]
}> = {
  product_mvp: {
    dialogTitle: 'Clarify MVP',
    goalText: 'Goal: define enough MVP context to start a kickoff meeting.',
    previewTitle: 'MVP Brief Preview',
    fields: [
      { key: 'summary', label: 'MVP Summary' },
      { key: 'goals', label: 'MVP Must-haves' },
      { key: 'acceptance_criteria', label: 'Success Criteria' },
      { key: 'risks', label: 'Risks / Unknowns' },
    ],
  },
  change_request: {
    dialogTitle: 'Clarify Change',
    goalText: 'Goal: clarify how this request changes the current product.',
    previewTitle: 'Change Request Preview',
    fields: [
      { key: 'summary', label: 'Change Summary' },
      { key: 'goals', label: 'User Value' },
      { key: 'acceptance_criteria', label: 'Acceptance Criteria' },
      { key: 'risks', label: 'Dependencies / Conflicts' },
    ],
  },
}

function isFieldComplete(ctx: MeetingContextDraft | null, key: keyof MeetingContextDraft): boolean {
  if (!ctx) return false
  const value = ctx[key]
  if (Array.isArray(value)) return value.length > 0
  return typeof value === 'string' && value.length > 0 && value !== 'pending'
}

export function RequirementClarificationDialog({
  workspace,
  requirementId,
  requirementTitle,
  requirementKind,
  open,
  onOpenChange,
}: Props) {
  const [message, setMessage] = useState('')
  const [session, setSession] = useState<ClarificationSession | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const config = MODE_CONFIG[requirementKind]

  const startMutation = useMutation({
    mutationFn: () => clarificationsApi.start(workspace, requirementId),
    onSuccess: (data) => setSession(data.session),
  })

  const sendMutation = useMutation({
    mutationFn: (msg: string) =>
      clarificationsApi.sendMessage(workspace, requirementId, session!.id, msg),
    onSuccess: (data) => {
      setSession(data.session)
      setMessage('')
    },
  })

  const kickoffMutation = useMutation({
    mutationFn: () =>
      clarificationsApi.kickoff(workspace, requirementId, session!.id),
    onSuccess: () => onOpenChange(false),
  })

  useEffect(() => {
    if (open && !session) startMutation.mutate()
  }, [open])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session?.messages?.length])

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim() || sendMutation.isPending) return
    sendMutation.mutate(message.trim())
  }

  const canKickoff = session?.readiness?.ready && !kickoffMutation.isPending
  const ctx = session?.meeting_context ?? null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {config.dialogTitle}: {requirementTitle}
            {session && (
              <Badge variant={session.status === 'ready' ? 'default' : 'secondary'}>
                {session.status}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>

        <p className="text-sm text-muted-foreground -mt-2 mb-2">{config.goalText}</p>

        <div className="flex gap-4 min-h-[400px]">
          {/* Chat */}
          <div className="flex-1 flex flex-col">
            <div className="flex-1 overflow-y-auto space-y-3 mb-3 pr-2">
              {session?.messages.map((msg, i) => (
                <div key={i} className={`p-2 rounded text-sm ${msg.role === 'user' ? 'bg-blue-50 ml-8' : 'bg-gray-50 mr-8'}`}>
                  <span className="text-xs text-muted-foreground block mb-1">
                    {msg.role === 'user' ? 'You' : 'Agent'}
                  </span>
                  {msg.content}
                </div>
              ))}
              {sendMutation.isPending && (
                <div className="bg-gray-50 mr-8 p-2 rounded text-sm text-muted-foreground">Thinking...</div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSend} className="flex gap-2">
              <Input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={
                  requirementKind === 'product_mvp'
                    ? 'Describe the MVP feature...'
                    : 'Describe the change...'
                }
                disabled={sendMutation.isPending}
                className="flex-1"
              />
              <Button type="submit" disabled={!message.trim() || sendMutation.isPending}>Send</Button>
            </form>
          </div>

          {/* Context preview */}
          <div className="w-72 border-l pl-4 space-y-3 overflow-y-auto">
            <h4 className="font-medium text-sm">{config.previewTitle}</h4>

            {config.fields.map(({ key, label }) => (
              <div key={key}>
                <div className="flex items-center gap-1 text-sm">
                  <span className={isFieldComplete(ctx, key) ? 'text-green-600' : 'text-amber-500'}>
                    {isFieldComplete(ctx, key) ? '\u2713' : '\u25CB'}
                  </span>
                  <span className="font-medium">{label}</span>
                </div>
                {ctx && (
                  <ul className="text-xs text-muted-foreground ml-4 mt-1 space-y-0.5">
                    {(Array.isArray(ctx[key]) ? ctx[key] : [ctx[key]]).map(
                      (item, i) => typeof item === 'string' && item !== 'pending' && <li key={i}>{item}</li>
                    )}
                  </ul>
                )}
              </div>
            ))}

            {ctx?.validated_attendees && ctx.validated_attendees.length > 0 && (
              <div>
                <span className="font-medium text-sm">Suggested Attendees</span>
                <div className="flex gap-1 mt-1 flex-wrap">
                  {ctx.validated_attendees.map((a) => (
                    <Badge key={a} variant="outline" className="text-xs">{a}</Badge>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-4 border-t">
              <Button className="w-full" disabled={!canKickoff} onClick={() => kickoffMutation.mutate()}>
                {kickoffMutation.isPending ? 'Starting...' : 'Start Kickoff Meeting'}
              </Button>
              {session?.readiness && !session.readiness.ready && (
                <p className="text-xs text-amber-600 mt-1">
                  Missing: {session.readiness.missing_fields.join(', ')}
                </p>
              )}
              {kickoffMutation.isError && (
                <p className="text-xs text-red-600 mt-1">{String(kickoffMutation.error)}</p>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: Errors in `RequirementsBoard.tsx` due to changed props — fixed in Task 7

- [ ] **Step 3: Commit**

```bash
git add web/src/components/common/RequirementClarificationDialog.tsx
git commit -m "feat: mode-aware clarification dialog (MVP vs Change Request)"
```

---

### Task 7: Rewrite RequirementsBoard as Product Workbench

**Files:**
- Modify: `web/src/pages/RequirementsBoard.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Rewrite RequirementsBoard.tsx**

Replace the page with the product workbench layout. Uses the new header, lifecycle board, and mode-aware dialogs.

```tsx
// web/src/pages/RequirementsBoard.tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { ProductWorkbenchHeader } from '@/components/board/ProductWorkbenchHeader'
import { ProductLifecycleBoard } from '@/components/board/ProductLifecycleBoard'
import { CreateRequirementDialog } from '@/components/common/CreateRequirementDialog'
import { RequirementClarificationDialog } from '@/components/common/RequirementClarificationDialog'
import { PoolStatusBar } from '@/components/common/PoolStatusBar'
import { requirementsApi } from '@/lib/api'
import { useWorkspace } from '@/lib/workspace'
import { useWebSocket } from '@/hooks/useWebSocket'
import { deriveProductWorkbenchState } from '@/lib/product-workbench'

export function RequirementsBoard() {
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()
  const { connected, subscribe } = useWebSocket()
  const [clarifyReq, setClarifyReq] = useState<{ id: string; title: string } | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  const { data: requirements, isLoading, error } = useQuery({
    queryKey: ['requirements', workspace],
    queryFn: () => requirementsApi.list(workspace),
  })

  useEffect(() => {
    if (connected) {
      subscribe(workspace)
    }
  }, [connected, workspace, subscribe])

  useEffect(() => {
    const handleMessage = (e: Event) => {
      const message = (e as CustomEvent).detail
      if (message.type === 'entity_changed' && message.entity_type === 'requirement') {
        queryClient.invalidateQueries({ queryKey: ['requirements'] })
      }
    }

    window.addEventListener('ws-message', handleMessage as EventListener)
    return () => {
      window.removeEventListener('ws-message', handleMessage as EventListener)
    }
  }, [queryClient])

  const handleCardClick = (id: string) => {
    console.log('Clicked requirement:', id)
  }

  const workbench = deriveProductWorkbenchState(requirements || [])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">Loading product workbench...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-red-600">Error loading requirements: {error.message}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8 space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Current Product Workbench</h1>

        <ProductWorkbenchHeader
          baselineStatus={workbench.baselineStatus}
          onCreateRequirement={() => setShowCreate(true)}
          onContinueClarifying={() => {
            if (workbench.mvpRequirement) {
              setClarifyReq({
                id: workbench.mvpRequirement.id,
                title: workbench.mvpRequirement.title,
              })
            }
          }}
          mvpRequirementId={workbench.mvpRequirement?.id}
        />

        {requirements && requirements.length > 0 ? (
          <ProductLifecycleBoard
            requirements={requirements}
            onCardClick={handleCardClick}
            workspace={workspace}
            onClarify={(id, title) => setClarifyReq({ id, title })}
            requirementKinds={workbench.requirementKinds}
          />
        ) : (
          <div className="bg-white rounded-lg shadow-md p-8 text-center">
            <p className="text-gray-500 mb-2">No requirements yet</p>
            <p className="text-gray-400 text-sm">Create your first requirement to define the product MVP.</p>
          </div>
        )}

        <div className="mt-6">
          <PoolStatusBar />
        </div>
      </div>

      {showCreate && (
        <CreateRequirementDialog
          workspace={workspace}
          baselineStatus={workbench.baselineStatus}
        />
      )}

      {clarifyReq && (
        <RequirementClarificationDialog
          workspace={workspace}
          requirementId={clarifyReq.id}
          requirementTitle={clarifyReq.title}
          requirementKind={workbench.requirementKinds.get(clarifyReq.id) || 'product_mvp'}
          open={!!clarifyReq}
          onOpenChange={(open) => { if (!open) setClarifyReq(null) }}
        />
      )}
    </div>
  )
}
```

Note: `CreateRequirementDialog` is rendered as a controlled dialog via `showCreate` state. The component's internal `DialogTrigger` still works but is now unused since we trigger it from the header button. The component needs a small adjustment to support being opened externally. See the updated component below.

Actually, since `CreateRequirementDialog` uses `DialogTrigger`, it controls its own open state. To open it from the header button, we need to make it accept an `open`/`onOpenChange` pair like `RequirementClarificationDialog` does. Update `CreateRequirementDialog` to accept optional controlled props:

Add to the existing `CreateRequirementDialog` (from Task 5), change the interface and Dialog usage:

```tsx
// Updated interface for CreateRequirementDialog
interface CreateRequirementDialogProps {
  workspace: string
  baselineStatus: BaselineStatus
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

// Updated Dialog usage (replace the existing Dialog line):
// In the component body, merge internal and external open state:
export function CreateRequirementDialog({ workspace, baselineStatus, open: externalOpen, onOpenChange: externalOnOpenChange }: CreateRequirementDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false)
  const open = externalOpen !== undefined ? externalOpen : internalOpen
  const setOpen = (val: boolean) => {
    setInternalOpen(val)
    externalOnOpenChange?.(val)
  }
  // ... rest stays the same but remove DialogTrigger, just render the Dialog directly

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {!externalOpen && (
        <DialogTrigger asChild>
          <Button>{config.buttonLabel}</Button>
        </DialogTrigger>
      )}
      <DialogContent>
        {/* ... same form content ... */}
      </DialogContent>
    </Dialog>
  )
}
```

This approach lets the dialog work both standalone (with its own trigger button) and controlled (opened by the header).

- [ ] **Step 2: Update App.tsx nav label**

Change the "Requirements" nav link to "Workbench":

In `web/src/App.tsx`, change:
```tsx
<Link to="/requirements" className="hover:underline">Requirements</Link>
```
to:
```tsx
<Link to="/requirements" className="hover:underline">Workbench</Link>
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/RequirementsBoard.tsx web/src/App.tsx web/src/components/common/CreateRequirementDialog.tsx
git commit -m "feat: rewrite RequirementsBoard as Product Workbench with lifecycle board"
```

---

### Task 8: Verify and Fix Build

**Files:**
- All modified files

- [ ] **Step 1: Run TypeScript compilation**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Run Vite build**

Run: `cd web && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Fix any issues**

If any TypeScript errors or build failures, fix them inline.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve build issues for product workbench frontend"
```

---

## Self-Review

**1. Spec coverage:**

| Spec Requirement | Task |
|---|---|
| Product status card (3 states) | Task 2 |
| Requirement kinds (MVP vs Change Request) | Task 1 (types) + Task 4 (badge) |
| Lifecycle board columns (8 columns) | Task 3 |
| Card design with kind badge + next action | Task 4 |
| Mode-aware clarification dialog | Task 6 |
| Mode-aware create dialog | Task 5 |
| Page title "Current Product Workbench" | Task 7 |
| Baseline visibility (empty state) | Task 2 (header) |
| No multi-product UI | All tasks (no product switcher anywhere) |
| Derived frontend state | Task 1 (deriveProductWorkbenchState) |
| Nav label update | Task 7 (App.tsx) |

**2. Placeholder scan:** No TBD/TODO/placeholders. All code provided.

**3. Type consistency:** `RequirementKind` = `'product_mvp' | 'change_request'` used consistently across `product-workbench.ts`, `ProductLifecycleBoard.tsx`, `RequirementCard.tsx`, `RequirementClarificationDialog.tsx`, and `RequirementsBoard.tsx`. `BaselineStatus` = `'not_started' | 'defining_mvp' | 'active'` used in `ProductWorkbenchHeader.tsx`, `CreateRequirementDialog.tsx`, `RequirementsBoard.tsx`.
