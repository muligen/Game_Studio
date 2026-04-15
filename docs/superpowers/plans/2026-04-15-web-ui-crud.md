# Web UI CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add create and status transition functionality to the Web UI for requirements and bugs.

**Architecture:** Dialog components for forms, dropdown menu for status transitions. All backend APIs already exist — frontend only.

**Tech Stack:** React 18, TypeScript, Tanstack Query, shadcn/ui Dialog, native HTML select for dropdowns

---

## File Structure

```
web/src/components/common/
├── CreateRequirementDialog.tsx   # New — form dialog
├── CreateBugDialog.tsx           # New — form dialog
└── TransitionMenu.tsx            # New — status dropdown

web/src/components/ui/
└── dialog.tsx                    # New — shadcn Dialog component

web/src/components/board/
└── RequirementCard.tsx           # Modify — add TransitionMenu

web/src/pages/
├── RequirementsBoard.tsx         # Modify — add CreateRequirementDialog
└── BugsBoard.tsx                 # Modify — add CreateBugDialog + TransitionMenu
```

---

## Task 1: Add Dialog Component

**Files:**
- Create: `web/src/components/ui/dialog.tsx`
- Modify: `web/package.json`

- [ ] **Step 1: Install Radix Dialog dependency**

Run: `cd web && npm install @radix-ui/react-dialog`

- [ ] **Step 2: Create dialog.tsx**

```typescript
// web/src/components/ui/dialog.tsx
import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { cn } from "@/lib/utils"

const Dialog = DialogPrimitive.Root
const DialogTrigger = DialogPrimitive.Trigger
const DialogClose = DialogPrimitive.Close
const DialogPortal = DialogPrimitive.Portal

const DialogOverlay = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
))
DialogOverlay.displayName = "DialogOverlay"

const DialogContent = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-white p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
        className
      )}
      {...props}
    >
      {children}
    </DialogPrimitive.Content>
  </DialogPortal>
))
DialogContent.displayName = "DialogContent"

const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)} {...props} />
)

const DialogTitle = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight", className)}
    {...props}
  />
))
DialogTitle.displayName = "DialogTitle"

export {
  Dialog,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogTitle,
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add web/src/components/ui/dialog.tsx web/package.json web/package-lock.json
git commit -m "feat(web): add Dialog component"
```

---

## Task 2: Create CreateRequirementDialog

**Files:**
- Create: `web/src/components/common/CreateRequirementDialog.tsx`

- [ ] **Step 1: Create the dialog component**

```typescript
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

interface CreateRequirementDialogProps {
  workspace: string
}

const PRIORITIES = ['low', 'medium', 'high'] as const

export function CreateRequirementDialog({ workspace }: CreateRequirementDialogProps) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<'low' | 'medium' | 'high'>('medium')
  const queryClient = useQueryClient()

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
        <Button>Create Requirement</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Requirement</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter requirement title"
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
              Error: {createMutation.error.message}
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
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/common/CreateRequirementDialog.tsx
git commit -m "feat(web): add CreateRequirementDialog component"
```

---

## Task 3: Create CreateBugDialog

**Files:**
- Create: `web/src/components/common/CreateBugDialog.tsx`

- [ ] **Step 1: Create the dialog component**

```typescript
// web/src/components/common/CreateBugDialog.tsx
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
import { bugsApi } from '@/lib/api'

interface CreateBugDialogProps {
  workspace: string
}

const SEVERITIES = ['low', 'medium', 'high', 'critical'] as const

export function CreateBugDialog({ workspace }: CreateBugDialogProps) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [severity, setSeverity] = useState<'low' | 'medium' | 'high' | 'critical'>('medium')
  const [requirementId, setRequirementId] = useState('')
  const queryClient = useQueryClient()

  const createMutation = useMutation({
    mutationFn: () => bugsApi.create(workspace, requirementId || 'unknown', title, severity),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bugs'] })
      setOpen(false)
      setTitle('')
      setSeverity('medium')
      setRequirementId('')
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
        <Button>Create Bug</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Bug</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter bug title"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Severity</label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value as 'low' | 'medium' | 'high' | 'critical')}
              className="w-full h-10 rounded-md border border-gray-300 px-3 text-sm"
            >
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Requirement ID (optional)</label>
            <Input
              value={requirementId}
              onChange={(e) => setRequirementId(e.target.value)}
              placeholder="e.g. req_1a89dc49"
            />
          </div>
          {createMutation.error && (
            <p className="text-sm text-red-600">
              Error: {createMutation.error.message}
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
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/common/CreateBugDialog.tsx
git commit -m "feat(web): add CreateBugDialog component"
```

---

## Task 4: Create TransitionMenu Component

**Files:**
- Create: `web/src/components/common/TransitionMenu.tsx`

- [ ] **Step 1: Create the transition menu component**

```typescript
// web/src/components/common/TransitionMenu.tsx
import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { requirementsApi, bugsApi } from '@/lib/api'

interface TransitionMenuProps {
  entityType: 'requirement' | 'bug'
  id: string
  currentStatus: string
  workspace: string
  allStatuses: readonly string[]
  onSuccess?: () => void
}

export function TransitionMenu({
  entityType,
  id,
  currentStatus,
  workspace,
  allStatuses,
  onSuccess,
}: TransitionMenuProps) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const transitionMutation = useMutation({
    mutationFn: (nextStatus: string) => {
      if (entityType === 'requirement') {
        return requirementsApi.transition(workspace, id, nextStatus)
      }
      return bugsApi.transition(workspace, id, nextStatus)
    },
    onSuccess: () => {
      const queryKey = entityType === 'requirement' ? ['requirements'] : ['bugs']
      queryClient.invalidateQueries({ queryKey })
      setOpen(false)
      onSuccess?.()
    },
  })

  // Close menu when clicking outside
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const availableStatuses = allStatuses.filter((s) => s !== currentStatus)

  return (
    <div className="relative inline-block" ref={menuRef}>
      <Button
        variant="ghost"
        size="sm"
        onClick={(e) => {
          e.stopPropagation()
          setOpen(!open)
        }}
      >
        →
      </Button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-10 bg-white border rounded-md shadow-lg min-w-[180px]">
          {availableStatuses.map((status) => (
            <button
              key={status}
              className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 capitalize"
              onClick={(e) => {
                e.stopPropagation()
                transitionMutation.mutate(status)
              }}
              disabled={transitionMutation.isPending}
            >
              {status.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/common/TransitionMenu.tsx
git commit -m "feat(web): add TransitionMenu component"
```

---

## Task 5: Integrate Create Dialogs into Pages

**Files:**
- Modify: `web/src/pages/RequirementsBoard.tsx`
- Modify: `web/src/pages/BugsBoard.tsx`

- [ ] **Step 1: Update RequirementsBoard.tsx**

Replace the existing `handleCreate` function and the "Create Requirement" button with the dialog component.

Add import at the top:
```typescript
import { CreateRequirementDialog } from '@/components/common/CreateRequirementDialog'
```

Remove the `handleCreate` function (lines 48-52 with the alert).

Replace the `<Button onClick={handleCreate}>Create Requirement</Button>` with:
```typescript
<CreateRequirementDialog workspace={workspace} />
```

- [ ] **Step 2: Update BugsBoard.tsx**

Add imports at the top:
```typescript
import { CreateBugDialog } from '@/components/common/CreateBugDialog'
```

Add a "Create Bug" button next to the "Bugs" title. Replace:
```typescript
<h1 className="text-3xl font-bold text-gray-900">Bugs</h1>
```
With:
```typescript
<h1 className="text-3xl font-bold text-gray-900">Bugs</h1>
<CreateBugDialog workspace={workspace} />
```

- [ ] **Step 3: Verify TypeScript compiles and build succeeds**

Run: `cd web && npm run build`
Expected: Build successful

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/RequirementsBoard.tsx web/src/pages/BugsBoard.tsx
git commit -m "feat(web): integrate create dialogs into board pages"
```

---

## Task 6: Integrate TransitionMenu into Cards

**Files:**
- Modify: `web/src/components/board/RequirementCard.tsx`
- Modify: `web/src/pages/BugsBoard.tsx`

- [ ] **Step 1: Update RequirementCard to include TransitionMenu**

Add import:
```typescript
import { TransitionMenu } from '@/components/common/TransitionMenu'
```

Update the `RequirementCardProps` interface to add workspace:
```typescript
interface RequirementCardProps {
  id: string
  title: string
  status?: string
  priority?: string
  workspace: string
  onClick: () => void
}
```

Destructure `workspace` from props.

Add TransitionMenu inside the card, after the status badge. Add a flex container:
```typescript
<div className="flex items-center justify-between mt-2">
  <Badge className={STATUS_COLORS[statusValue] || STATUS_COLORS.draft}>
    {statusValue.replace(/_/g, ' ')}
  </Badge>
  <TransitionMenu
    entityType="requirement"
    id={id}
    currentStatus={statusValue}
    workspace={workspace}
    allStatuses={[
      'draft', 'designing', 'pending_user_review', 'approved',
      'implementing', 'self_test_passed', 'testing',
      'pending_user_acceptance', 'quality_check', 'done',
    ]}
  />
</div>
```

- [ ] **Step 2: Update KanbanBoard to pass workspace to RequirementCard**

In `web/src/components/board/KanbanBoard.tsx`, add `workspace` prop to the component interface and pass it to each RequirementCard:
```typescript
<RequirementCard
  key={card.id}
  {...card}
  workspace={workspace}
  onClick={() => onCardClick(card.id)}
/>
```

Update KanbanBoard props to accept workspace from parent.

Update RequirementsBoard to pass workspace to KanbanBoard.

- [ ] **Step 3: Update BugsBoard bug cards to include TransitionMenu**

Add import at top of BugsBoard.tsx:
```typescript
import { TransitionMenu } from '@/components/common/TransitionMenu'
```

Add TransitionMenu inside each bug card div, after the severity badge:
```typescript
<div className="flex items-center justify-between mt-2">
  <span className={`text-xs px-2 py-1 rounded inline-block ${SEVERITY_COLORS[bug.severity]}`}>
    {bug.severity}
  </span>
  <TransitionMenu
    entityType="bug"
    id={bug.id}
    currentStatus={bug.status}
    workspace={workspace}
    allStatuses={['new', 'fixing', 'fixed', 'verifying', 'closed', 'reopened', 'needs_user_decision']}
  />
</div>
```

- [ ] **Step 4: Verify TypeScript compiles and build succeeds**

Run: `cd web && npm run build`
Expected: Build successful

- [ ] **Step 5: Commit**

```bash
git add web/src/components/board/RequirementCard.tsx web/src/components/board/KanbanBoard.tsx web/src/pages/BugsBoard.tsx web/src/pages/RequirementsBoard.tsx
git commit -m "feat(web): add status transition menus to requirement and bug cards"
```

---

## Task 7: Final Verification

**Files:**
- None new

- [ ] **Step 1: Run backend tests**

Run: `uv run pytest -q`
Expected: All tests pass

- [ ] **Step 2: Run frontend build**

Run: `cd web && npm run build`
Expected: Build successful

- [ ] **Step 3: Manual smoke test**

1. Start backend: `uv run uvicorn studio.api.main:create_app --factory --reload`
2. Start frontend: `cd web && npm run dev`
3. Open http://localhost:5173/requirements
4. Click "Create Requirement" → fill form → submit → verify card appears
5. Click → on a requirement card → select new status → verify card moves
6. Open http://localhost:5173/bugs
7. Click "Create Bug" → fill form → submit → verify card appears
8. Click → on a bug card → select new status → verify card moves

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix(web): final CRUD integration fixes"
```

---

## Self-Review

**Spec coverage:**
- ✅ Create requirement dialog → Task 2 + Task 5
- ✅ Create bug dialog → Task 3 + Task 5
- ✅ Requirement status transition → Task 4 + Task 6
- ✅ Bug status transition → Task 4 + Task 6

**Placeholder scan:** No TBD, TODO, or vague steps found.

**Type consistency:** All component props, API methods, and status arrays match across tasks.
