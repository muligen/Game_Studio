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

interface Props {
  workspace: string
  requirementId: string
  requirementTitle: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

const REQUIRED_FIELDS: { key: keyof MeetingContextDraft; label: string }[] = [
  { key: 'summary', label: 'Summary' },
  { key: 'goals', label: 'Goals' },
  { key: 'acceptance_criteria', label: 'Criteria' },
  { key: 'risks', label: 'Risks' },
]

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
  open,
  onOpenChange,
}: Props) {
  const [message, setMessage] = useState('')
  const [session, setSession] = useState<ClarificationSession | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

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
      <DialogContent className="flex h-[80vh] max-w-4xl flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Clarify: {requirementTitle}
            {session && (
              <Badge variant={session.status === 'ready' ? 'default' : 'secondary'}>
                {session.status}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>

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
                placeholder="Describe the feature..."
                disabled={sendMutation.isPending}
                className="flex-1"
              />
              <Button type="submit" disabled={!message.trim() || sendMutation.isPending}>Send</Button>
            </form>
          </div>

          {/* Context preview */}
          <div className="min-h-0 w-72 shrink-0 space-y-3 overflow-y-auto border-l pl-4">
            <h4 className="font-medium text-sm">Context Preview</h4>

            {REQUIRED_FIELDS.map(({ key, label }) => (
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
                <span className="font-medium text-sm">Attendees</span>
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
