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
  open?: boolean
  onOpenChange?: (open: boolean) => void
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

export function CreateRequirementDialog({ workspace, baselineStatus, open: externalOpen, onOpenChange: externalOnOpenChange }: CreateRequirementDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false)
  const open = externalOpen !== undefined ? externalOpen : internalOpen
  const setOpen = (val: boolean) => {
    setInternalOpen(val)
    externalOnOpenChange?.(val)
  }
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
      {externalOpen === undefined && (
        <DialogTrigger asChild>
          <Button>{config.buttonLabel}</Button>
        </DialogTrigger>
      )}
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
