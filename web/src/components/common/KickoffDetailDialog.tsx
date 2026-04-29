import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { MeetingGraphProgress } from '@/components/common/MeetingGraphProgress'
import { MeetingTranscriptDialog } from '@/components/common/MeetingTranscriptDialog'
import {
  clarificationsApi,
  deliveryApi,
  type KickoffMeetingResult,
  type KickoffResponse,
  type KickoffTaskStatus,
} from '@/lib/api'

interface KickoffDetailDialogProps {
  workspace: string
  requirementId: string
  requirementTitle: string
  sessionId: string | null
  kickoffTaskId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onEditClarification: () => void
}

type DetailPhase =
  | 'kickoff_running'
  | 'kickoff_failed'
  | 'delivery_generating'
  | 'delivery_failed'
  | 'delivery_ready'

function phaseFromTask(task: KickoffTaskStatus | null): DetailPhase {
  if (!task) return 'kickoff_running'
  if (task.status === 'failed' && task.meeting_result) return 'delivery_failed'
  if (task.status === 'failed') return 'kickoff_failed'
  if (task.status === 'completed') return 'delivery_ready'
  return 'kickoff_running'
}

function resultFromTask(task: KickoffTaskStatus | null): KickoffMeetingResult | null {
  return task?.meeting_result ?? null
}

export function KickoffDetailDialog({
  workspace,
  requirementId,
  requirementTitle,
  sessionId,
  kickoffTaskId,
  open,
  onOpenChange,
  onEditClarification,
}: KickoffDetailDialogProps) {
  const navigate = useNavigate()
  const [taskId, setTaskId] = useState<string | null>(kickoffTaskId)
  const [task, setTask] = useState<KickoffTaskStatus | null>(null)
  const [phase, setPhase] = useState<DetailPhase>('kickoff_running')
  const [deliveryError, setDeliveryError] = useState<string | null>(null)
  const [transcriptOpen, setTranscriptOpen] = useState(false)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (open) {
      setTaskId(kickoffTaskId)
      setDeliveryError(null)
    } else {
      setTask(null)
      setTranscriptOpen(false)
      setElapsed(0)
    }
  }, [kickoffTaskId, open])

  useEffect(() => {
    if (!open || !taskId) return

    let stopped = false
    const poll = async () => {
      while (!stopped) {
        try {
          const nextTask = await clarificationsApi.getKickoffTask(workspace, taskId)
          if (stopped) return
          setTask(nextTask)
          setPhase(phaseFromTask(nextTask))
          if (nextTask.status === 'completed' || nextTask.status === 'failed') return
        } catch {
          return
        }
        await new Promise(resolve => setTimeout(resolve, 2000))
      }
    }

    poll()
    return () => {
      stopped = true
    }
  }, [open, taskId, workspace])

  useEffect(() => {
    if (!open || (phase !== 'kickoff_running' && phase !== 'delivery_generating')) {
      setElapsed(0)
      return
    }
    const startedAt = task?.started_at ? new Date(task.started_at).getTime() : Date.now()
    const start = Number.isNaN(startedAt) ? Date.now() : startedAt
    const id = setInterval(() => setElapsed(Math.max(0, Math.floor((Date.now() - start) / 1000))), 1000)
    return () => clearInterval(id)
  }, [open, phase, task?.started_at])

  const kickoffMutation = useMutation({
    mutationFn: (): Promise<KickoffResponse> => {
      if (!sessionId) throw new Error('Clarification session is missing.')
      return clarificationsApi.kickoff(workspace, requirementId, sessionId)
    },
    onSuccess: (response) => {
      setTask(null)
      setTaskId(response.task_id)
      setPhase('kickoff_running')
      setDeliveryError(null)
    },
  })

  const deliveryMutation = useMutation({
    mutationFn: ({ meetingId, projectId }: { meetingId: string; projectId: string }) =>
      deliveryApi.generatePlan(workspace, meetingId, projectId),
  })

  const result = resultFromTask(task)
  const meeting = result?.meeting ?? null
  const summary = meeting?.summary
  const activeAgents = task?.active_agents ?? []
  const errorText = deliveryError || task?.error || null

  const title = useMemo(() => {
    if (phase === 'kickoff_running') return 'Kickoff Running'
    if (phase === 'kickoff_failed') return 'Kickoff Failed'
    if (phase === 'delivery_generating') return 'Generating Delivery Plan'
    if (phase === 'delivery_failed') return 'Delivery Plan Failed'
    return 'Kickoff Complete'
  }, [phase])

  const openMeetingMinutes = useCallback(() => {
    if (!result) return
    const url = `/api/meetings/${result.meeting_id}?workspace=${encodeURIComponent(workspace)}`
    window.open(url, '_blank', 'noopener,noreferrer')
  }, [result, workspace])

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex max-h-[86vh] max-w-5xl flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {requirementTitle}
              <Badge variant="outline">{title}</Badge>
            </DialogTitle>
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
            <div className="rounded-md border bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm text-slate-700">
                  {phase === 'kickoff_running' && `Meeting is running. ${elapsed}s elapsed.`}
                  {phase === 'delivery_generating' && `Delivery task generation is running. ${elapsed}s elapsed.`}
                  {phase === 'kickoff_failed' && (errorText || 'Kickoff meeting failed.')}
                  {phase === 'delivery_failed' && (errorText || 'Kickoff completed, but delivery task generation failed.')}
                  {phase === 'delivery_ready' && 'Kickoff completed and delivery tasks are ready.'}
                </p>
                {activeAgents.length > 0 && (
                  <Badge variant="secondary">Active: {activeAgents.join(', ')}</Badge>
                )}
              </div>
            </div>

            <MeetingGraphProgress task={task} phase={phase} />

            {result && (
              <div className="space-y-3 text-sm text-slate-700">
                <div className="grid gap-2 rounded-md border bg-white p-3 md:grid-cols-2">
                  <p><span className="font-medium">Project ID:</span> {result.project_id}</p>
                  <p><span className="font-medium">Meeting ID:</span> {result.meeting_id}</p>
                </div>
                {summary && (
                  <div className="rounded-md border bg-white p-3">
                    <p className="mb-1 font-medium">Meeting Summary</p>
                    <p>{summary}</p>
                  </div>
                )}
                {meeting && (
                  <div className="rounded-md border bg-white p-3">
                    <p className="mb-1 font-medium">Attendees</p>
                    <p>{meeting.attendees.join(', ') || 'No attendees recorded.'}</p>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-wrap justify-end gap-2 border-t pt-3">
            {(phase === 'delivery_ready' || phase === 'delivery_generating') && (
              <Button
                onClick={() => {
                  onOpenChange(false)
                  navigate(`/delivery?requirement_id=${requirementId}`)
                }}
              >
                Open Delivery Board
              </Button>
            )}
            {result && (
              <Button variant="outline" onClick={() => setTranscriptOpen(true)}>
                View Meeting Transcript
              </Button>
            )}
            {result && (
              <Button variant="outline" onClick={openMeetingMinutes}>
                View Meeting Minutes
              </Button>
            )}
            {phase === 'delivery_failed' && result && (
              <Button
                variant="outline"
                disabled={deliveryMutation.isPending}
                onClick={() => {
                  setPhase('delivery_generating')
                  setDeliveryError(null)
                  deliveryMutation.mutate(
                    { meetingId: result.meeting_id, projectId: result.project_id },
                    {
                      onSuccess: () => setPhase('delivery_ready'),
                      onError: (error) => {
                        setPhase('delivery_failed')
                        setDeliveryError(
                          error instanceof Error ? error.message : 'Delivery generation failed.',
                        )
                      },
                    },
                  )
                }}
              >
                {deliveryMutation.isPending ? 'Retrying...' : 'Retry Generate Delivery Plan'}
              </Button>
            )}
            {phase === 'kickoff_failed' && (
              <>
                <Button
                  disabled={kickoffMutation.isPending || !sessionId}
                  onClick={() => kickoffMutation.mutate()}
                >
                  {kickoffMutation.isPending ? 'Retrying...' : 'Retry Kickoff'}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    onOpenChange(false)
                    onEditClarification()
                  }}
                >
                  Edit Clarification
                </Button>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <MeetingTranscriptDialog
        workspace={workspace}
        meetingId={result?.meeting_id ?? null}
        open={transcriptOpen}
        onOpenChange={setTranscriptOpen}
      />
    </>
  )
}
