import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { MeetingTranscriptDialog } from '@/components/common/MeetingTranscriptDialog'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  clarificationsApi,
  deliveryApi,
  type ClarificationSession,
  type KickoffMeetingResult,
  type KickoffResponse,
  type MeetingContextDraft,
} from '@/lib/api'
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

type KickoffUiState =
  | { phase: 'idle' }
  | { phase: 'already_completed' }
  | { phase: 'kickoff_running'; taskId: string; startTime: number }
  | { phase: 'kickoff_failed'; error: string }
  | { phase: 'delivery_generating'; result: KickoffMeetingResult }
  | { phase: 'delivery_failed'; result: KickoffMeetingResult; error: string }
  | { phase: 'delivery_ready'; result: KickoffMeetingResult }

export function RequirementClarificationDialog({
  workspace,
  requirementId,
  requirementTitle,
  requirementKind,
  open,
  onOpenChange,
}: Props) {
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  const [session, setSession] = useState<ClarificationSession | null>(null)
  const [kickoffUi, setKickoffUi] = useState<KickoffUiState>({ phase: 'idle' })
  const [transcriptOpen, setTranscriptOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const config = MODE_CONFIG[requirementKind]

  const startMutation = useMutation({
    mutationFn: () => clarificationsApi.start(workspace, requirementId),
    onSuccess: (data) => {
      setSession(data.session)
      if (data.session.status === 'completed' || data.session.status === 'kickoff_started') {
        setKickoffUi({ phase: 'already_completed' })
      }
    },
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
    onSuccess: (response: KickoffResponse) => {
      setKickoffUi({
        phase: 'kickoff_running',
        taskId: response.task_id,
        startTime: Date.now(),
      })
    },
    onError: (error) => {
      setKickoffUi({
        phase: 'kickoff_failed',
        error: error instanceof Error ? error.message : 'Kickoff failed.',
      })
    },
  })

  const deliveryMutation = useMutation({
    mutationFn: ({ meetingId, projectId }: { meetingId: string; projectId: string }) =>
      deliveryApi.generatePlan(workspace, meetingId, projectId),
  })

  // Poll kickoff task status
  useEffect(() => {
    if (kickoffUi.phase !== 'kickoff_running') return
    const { taskId } = kickoffUi

    const poll = async () => {
      try {
        const task = await clarificationsApi.getKickoffTask(workspace, taskId)

        if (task.status === 'completed' && task.meeting_result) {
          const result = task.meeting_result
          console.log('[kickoff] Meeting completed, generating delivery plan:', result.meeting_id, result.project_id)
          setKickoffUi({ phase: 'delivery_generating', result })
          deliveryMutation.mutate(
            { meetingId: result.meeting_id, projectId: result.project_id },
            {
              onSuccess: (data) => {
                console.log('[kickoff] Delivery plan generated:', data)
                setKickoffUi({ phase: 'delivery_ready', result })
              },
              onError: (error) => {
                console.error('[kickoff] Delivery plan failed:', error)
                setKickoffUi({
                  phase: 'delivery_failed',
                  result,
                  error: error instanceof Error ? error.message : 'Delivery generation failed.',
                })
              },
            },
          )
          return true
        }

        if (task.status === 'failed') {
          setKickoffUi({
            phase: 'kickoff_failed',
            error: task.error || 'Kickoff meeting failed.',
          })
          return true
        }

        return false
      } catch {
        return false
      }
    }

    let stopped = false
    const runPoll = async () => {
      while (!stopped) {
        const done = await poll()
        if (done) break
        await new Promise(resolve => setTimeout(resolve, 2000))
      }
    }
    runPoll()

    return () => { stopped = true }
  }, [kickoffUi.phase]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (open && !session) startMutation.mutate()
    if (!open) {
      setKickoffUi({ phase: 'idle' })
      setMessage('')
      setTranscriptOpen(false)
    }
  }, [open, session]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session?.messages?.length])

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim() || sendMutation.isPending || kickoffUi.phase !== 'idle') return
    sendMutation.mutate(message.trim())
  }

  const sessionCompleted = session?.status === 'completed' || session?.status === 'kickoff_started'
  const canKickoff = session?.readiness?.ready && !kickoffMutation.isPending && !sessionCompleted
  const ctx = session?.meeting_context ?? null
  const uiLocked = kickoffUi.phase !== 'idle'
  const kickoffResult =
    'result' in kickoffUi ? kickoffUi.result : null
  const kickoffMeeting = kickoffResult?.meeting ?? null

  const openMeetingMinutes = useCallback(() => {
    if (!kickoffResult) return
    const url = `/api/meetings/${kickoffResult.meeting_id}?workspace=${encodeURIComponent(workspace)}`
    window.open(url, '_blank', 'noopener,noreferrer')
  }, [kickoffResult, workspace])

  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (kickoffUi.phase !== 'kickoff_running' && kickoffUi.phase !== 'delivery_generating') {
      setElapsed(0)
      return
    }
    const start = kickoffUi.phase === 'kickoff_running' ? kickoffUi.startTime : Date.now()
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(id)
  }, [kickoffUi.phase]) // eslint-disable-line react-hooks/exhaustive-deps

  const renderKickoffState = () => {
    if (kickoffUi.phase === 'idle') return null

    if (kickoffUi.phase === 'already_completed') {
      return (
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <div className="w-full max-w-2xl space-y-4 rounded-lg border bg-slate-50 p-6">
            <Badge variant="outline">Kickoff Completed</Badge>
            <h3 className="text-lg font-semibold text-slate-900">{requirementTitle}</h3>
            <p className="text-sm text-slate-600">
              The kickoff meeting for this requirement has already been completed.
            </p>
            <div className="flex gap-2">
              <Button onClick={() => { onOpenChange(false); navigate('/delivery') }}>
                Open Delivery Board
              </Button>
            </div>
          </div>
        </div>
      )
    }

    const summary = kickoffMeeting?.summary
    const consensus = kickoffMeeting?.consensus_points ?? []
    const conflicts = kickoffMeeting?.conflict_points ?? []

    return (
      <div className="flex min-h-0 flex-1 items-center justify-center">
        <div className="w-full max-w-2xl space-y-4 rounded-lg border bg-slate-50 p-6">
          <div className="space-y-2">
            <Badge variant="outline">
              {kickoffUi.phase === 'kickoff_running' && 'Kickoff Running'}
              {kickoffUi.phase === 'delivery_generating' && 'Generating Delivery Plan'}
              {kickoffUi.phase === 'kickoff_failed' && 'Kickoff Failed'}
              {kickoffUi.phase === 'delivery_failed' && 'Delivery Generation Failed'}
              {kickoffUi.phase === 'delivery_ready' && 'Kickoff Complete'}
            </Badge>
            <h3 className="text-lg font-semibold text-slate-900">{requirementTitle}</h3>
            <p className="text-sm text-slate-600">
              {kickoffUi.phase === 'kickoff_running' &&
                `The system is running the kickoff meeting now. (${elapsed}s elapsed)`}
              {kickoffUi.phase === 'delivery_generating' &&
                `Kickoff finished. Generating delivery tasks... (${elapsed}s elapsed)`}
              {kickoffUi.phase === 'kickoff_failed' && kickoffUi.error}
              {kickoffUi.phase === 'delivery_failed' &&
                'Kickoff completed, but delivery task generation failed.'}
              {kickoffUi.phase === 'delivery_ready' &&
                'Kickoff completed and delivery tasks are ready on the board.'}
            </p>
            {kickoffUi.phase === 'kickoff_running' && elapsed > 30 && (
              <p className="text-xs text-amber-600">
                Kickoff meetings typically take 1-3 minutes. Please wait...
              </p>
            )}
            {kickoffUi.phase === 'delivery_generating' && elapsed > 15 && (
              <p className="text-xs text-amber-600">
                Delivery plan generation is running...
              </p>
            )}
          </div>

          {kickoffResult && (
            <div className="space-y-3 text-sm text-slate-700">
              <div className="grid gap-2 rounded-md border bg-white p-3 md:grid-cols-2">
                <p><span className="font-medium">Project ID:</span> {kickoffResult.project_id}</p>
                <p><span className="font-medium">Meeting ID:</span> {kickoffResult.meeting_id}</p>
              </div>
              {summary && (
                <div className="rounded-md border bg-white p-3">
                  <p className="mb-1 font-medium">Meeting Summary</p>
                  <p>{summary}</p>
                </div>
              )}
              {kickoffMeeting && (
                <div className="rounded-md border bg-white p-3">
                  <p className="mb-1 font-medium">Attendees</p>
                  <p>{kickoffMeeting.attendees.join(', ') || 'No attendees recorded.'}</p>
                </div>
              )}
              {consensus.length > 0 && (
                <div className="rounded-md border bg-white p-3">
                  <p className="mb-1 font-medium">Consensus</p>
                  <ul className="list-disc space-y-1 pl-5">
                    {consensus.slice(0, 3).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {conflicts.length > 0 && (
                <div className="rounded-md border bg-white p-3">
                  <p className="mb-1 font-medium">Conflicts</p>
                  <ul className="list-disc space-y-1 pl-5">
                    {conflicts.slice(0, 3).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {kickoffUi.phase === 'delivery_failed' && (
            <p className="text-sm text-red-600">{kickoffUi.error}</p>
          )}

          <div className="flex flex-wrap gap-2">
            {(kickoffUi.phase === 'delivery_ready' || kickoffUi.phase === 'delivery_generating') && (
              <Button
                onClick={() => {
                  onOpenChange(false)
                  navigate('/delivery')
                }}
              >
                Open Delivery Board
              </Button>
            )}
            {kickoffResult && kickoffUi.phase !== 'kickoff_failed' && (
              <Button variant="outline" onClick={() => setTranscriptOpen(true)}>
                View Meeting Transcript
              </Button>
            )}
            {kickoffResult && kickoffUi.phase !== 'kickoff_failed' && (
              <Button variant="outline" onClick={openMeetingMinutes}>
                View Meeting Minutes
              </Button>
            )}
            {kickoffUi.phase === 'delivery_failed' && kickoffResult && (
              <Button
                variant="outline"
                onClick={() => {
                  setKickoffUi({ phase: 'delivery_generating', result: kickoffResult })
                  deliveryMutation.mutate(
                    { meetingId: kickoffResult.meeting_id, projectId: kickoffResult.project_id },
                    {
                      onSuccess: () => setKickoffUi({ phase: 'delivery_ready', result: kickoffResult }),
                      onError: (error) =>
                        setKickoffUi({
                          phase: 'delivery_failed',
                          result: kickoffResult,
                          error:
                            error instanceof Error
                              ? error.message
                              : 'Delivery generation failed.',
                        }),
                    },
                  )
                }}
              >
                Retry Generate Delivery Plan
              </Button>
            )}
            {kickoffUi.phase === 'kickoff_failed' && (
              <Button variant="outline" onClick={() => setKickoffUi({ phase: 'idle' })}>
                Back To Clarification
              </Button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex h-[80vh] max-w-4xl flex-col overflow-hidden">
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

          {kickoffUi.phase !== 'idle' ? renderKickoffState() : (
          <div className="flex min-h-0 flex-1 gap-4">
            {/* Chat */}
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              <div className="mb-3 min-h-0 flex-1 space-y-3 overflow-y-auto pr-2">
                {session?.messages.map((msg, i) => (
                  <div key={i} className={`whitespace-pre-wrap break-words rounded p-2 text-sm ${msg.role === 'user' ? 'bg-blue-50 ml-8' : 'bg-gray-50 mr-8'}`}>
                    <span className="text-xs text-muted-foreground block mb-1">
                      {msg.role === 'user' ? 'You' : 'Agent'}
                    </span>
                    {msg.content}
                  </div>
                ))}
                {sendMutation.isPending && (
                  <div className="bg-gray-50 mr-8 p-2 rounded text-sm text-muted-foreground">Thinking...</div>
                )}
                {sendMutation.isError && (
                  <div className="bg-red-50 border border-red-200 text-red-700 mr-8 p-2 rounded text-sm">
                    {sendMutation.error instanceof Error
                      ? sendMutation.error.message
                      : 'Clarification agent failed.'}
                  </div>
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
                  disabled={sendMutation.isPending || uiLocked}
                  className="flex-1"
                />
                <Button type="submit" disabled={!message.trim() || sendMutation.isPending || uiLocked}>Send</Button>
              </form>
            </div>

            {/* Context preview */}
            <div className="min-h-0 w-72 shrink-0 space-y-3 overflow-y-auto border-l pl-4">
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
                <Button className="w-full" disabled={!canKickoff || uiLocked} onClick={() => kickoffMutation.mutate()}>
                  {kickoffMutation.isPending ? 'Starting...' : 'Start Kickoff Meeting'}
                </Button>
                {sessionCompleted && (
                  <p className="text-xs text-slate-500 mt-1">Kickoff already completed.</p>
                )}
                {session?.readiness && !session.readiness.ready && !sessionCompleted && (
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
          )}
        </DialogContent>
      </Dialog>

      <MeetingTranscriptDialog
        workspace={workspace}
        meetingId={kickoffResult?.meeting_id ?? null}
        open={transcriptOpen}
        onOpenChange={setTranscriptOpen}
      />
    </>
  )
}
