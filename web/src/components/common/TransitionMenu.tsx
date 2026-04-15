import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { requirementsApi, bugsApi, type RequirementCard, type BugCard, type TransitionRequirementRequest } from '@/lib/api'

type RequirementStatus = TransitionRequirementRequest['next_status']
type BugStatus = BugCard['status']

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
                transitionMutation.mutate(status)
              }}
              disabled={transitionMutation.isPending}
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
  )
}
