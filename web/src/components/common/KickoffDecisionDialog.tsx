import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deliveryApi } from '@/lib/api'
import type { KickoffDecisionGate } from '@/lib/api'

interface KickoffDecisionDialogProps {
  gate: KickoffDecisionGate
  workspace: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function KickoffDecisionDialog({
  gate,
  workspace,
  open,
  onOpenChange,
}: KickoffDecisionDialogProps) {
  const [selections, setSelections] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {}
    for (const item of gate.items) {
      init[item.id] = ''
    }
    return init
  })
  const queryClient = useQueryClient()

  const resolveMutation = useMutation({
    mutationFn: () => deliveryApi.resolveGate(workspace, gate.id, selections),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['delivery-board'] })
      onOpenChange(false)
    },
  })

  const allSelected = gate.items.every((item) => selections[item.id])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Resolve Kickoff Decisions</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {gate.items.map((item) => (
            <div key={item.id}>
              <p className="font-medium text-sm">{item.question}</p>
              <p className="text-xs text-muted-foreground mb-2">{item.context}</p>
              <select
                value={selections[item.id]}
                onChange={(e) =>
                  setSelections((prev) => ({ ...prev, [item.id]: e.target.value }))
                }
                className="w-full h-10 rounded-md border border-gray-300 px-3 text-sm"
              >
                <option value="">Select an option...</option>
                {item.options.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>
          ))}
          {resolveMutation.error && (
            <p className="text-sm text-red-600">Error: {String(resolveMutation.error)}</p>
          )}
          <div className="flex justify-end gap-3">
            <DialogClose asChild>
              <Button type="button" variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              onClick={() => resolveMutation.mutate()}
              disabled={!allSelected || resolveMutation.isPending}
            >
              {resolveMutation.isPending ? 'Resolving...' : 'Resolve'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
