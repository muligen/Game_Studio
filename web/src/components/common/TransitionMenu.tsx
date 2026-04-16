import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { requirementsApi, bugsApi, designDocsApi, type RequirementCard, type BugCard, type TransitionRequirementRequest } from '@/lib/api'

type RequirementStatus = TransitionRequirementRequest['next_status']
type BugStatus = BugCard['status']

interface TransitionMenuProps {
  entityType: 'requirement' | 'bug'
  id: string
  currentStatus: string
  workspace: string
  allStatuses: readonly string[]
  designDocId?: string | null
  onSuccess?: () => void
}

export function TransitionMenu({
  entityType,
  id,
  currentStatus,
  workspace,
  allStatuses,
  designDocId,
  onSuccess,
}: TransitionMenuProps) {
  const [open, setOpen] = useState(false)
  const [sendBackOpen, setSendBackOpen] = useState(false)
  const [sendBackReason, setSendBackReason] = useState('')
  const menuRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const transitionMutation = useMutation({
    mutationFn: (nextStatus: string): Promise<RequirementCard | BugCard> => {
      if (entityType === 'requirement') {
        return requirementsApi.transition(workspace, id, nextStatus as RequirementStatus)
      }
      return bugsApi.transition(workspace, id, nextStatus as BugStatus)
    },
    onSuccess: () => {
      const queryKey = entityType === 'requirement' ? ['requirements'] : ['bugs']
      queryClient.invalidateQueries({ queryKey })
      setOpen(false)
      onSuccess?.()
    },
  })

  const sendBackMutation = useMutation({
    mutationFn: (reason: string) => designDocsApi.sendBack(workspace, designDocId!, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements'] })
      queryClient.invalidateQueries({ queryKey: ['design-doc'] })
      setSendBackOpen(false)
      setSendBackReason('')
      setOpen(false)
      onSuccess?.()
    },
  })

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

  const availableStatuses = allStatuses.filter((status) => status !== currentStatus)

  function handleTransition(status: string) {
    if (status === 'designing' && entityType === 'requirement' && designDocId) {
      setSendBackOpen(true)
    } else {
      transitionMutation.mutate(status)
    }
  }

  return (
    <>
      <div className="relative inline-block" ref={menuRef}>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            setOpen(!open)
          }}
        >
          Next
        </Button>
        {open && (
          <div className="absolute right-0 top-full mt-1 z-10 min-w-[180px] rounded-md border bg-white shadow-lg">
            {availableStatuses.length === 0 && (
              <div className="px-3 py-2 text-sm text-gray-500">
                No valid transitions
              </div>
            )}
            {availableStatuses.map((status) => (
              <button
                key={status}
                className="w-full px-3 py-2 text-left text-sm capitalize hover:bg-gray-100"
                onClick={(e) => {
                  e.stopPropagation()
                  handleTransition(status)
                }}
                disabled={transitionMutation.isPending || sendBackMutation.isPending}
              >
                {status.replace(/_/g, ' ')}
              </button>
            ))}
            {transitionMutation.error && (
              <div className="border-t px-3 py-2 text-xs text-red-600">
                {transitionMutation.error.message}
              </div>
            )}
          </div>
        )}
      </div>

      <Dialog open={sendBackOpen} onOpenChange={setSendBackOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send Back for Revision</DialogTitle>
          </DialogHeader>
          <textarea
            className="w-full min-h-[120px] p-3 border rounded"
            placeholder="Describe what needs to be changed..."
            value={sendBackReason}
            onChange={(e) => setSendBackReason(e.target.value)}
            onClick={(e) => e.stopPropagation()}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setSendBackOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (sendBackReason.trim()) {
                  sendBackMutation.mutate(sendBackReason.trim())
                }
              }}
              disabled={!sendBackReason.trim() || sendBackMutation.isPending}
            >
              {sendBackMutation.isPending ? 'Sending...' : 'Send Back'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
