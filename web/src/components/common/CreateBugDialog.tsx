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
