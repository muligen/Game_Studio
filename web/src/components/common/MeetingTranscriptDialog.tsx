import { useQuery } from '@tanstack/react-query'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { meetingsApi, type MeetingTranscriptEntry } from '@/lib/api'

interface MeetingTranscriptDialogProps {
  workspace: string
  meetingId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function getEntryTitle(entry: MeetingTranscriptEntry): string {
  return entry.label || entry.speaker || entry.agent_role || entry.role || entry.node_name || 'Transcript Entry'
}

function getEntryBody(entry: MeetingTranscriptEntry): string {
  return (
    entry.content ||
    entry.summary ||
    entry.message ||
    entry.reply ||
    entry.raw_reply ||
    'No transcript text recorded.'
  )
}

function getRoleTone(entry: MeetingTranscriptEntry): string {
  const role = `${entry.role || entry.speaker || entry.agent_role || ''}`.toLowerCase()
  if (role.includes('user') || role.includes('human')) {
    return 'self-end rounded-2xl rounded-br-md border border-blue-200 bg-blue-50'
  }
  if (role.includes('assistant') || role.includes('agent') || role.includes('claude')) {
    return 'self-start rounded-2xl rounded-bl-md border border-slate-200 bg-white'
  }
  return 'self-start rounded-2xl border border-slate-200 bg-slate-50'
}

function formatTimestamp(value: string | null | undefined): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function MeetingTranscriptDialog({
  workspace,
  meetingId,
  open,
  onOpenChange,
}: MeetingTranscriptDialogProps) {
  const transcriptQuery = useQuery({
    queryKey: ['meeting-transcript', workspace, meetingId],
    queryFn: () => meetingsApi.getTranscript(workspace, meetingId!),
    enabled: open && Boolean(meetingId),
  })

  const transcript = transcriptQuery.data
  const transcriptEntries = transcript?.events ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-w-5xl flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>Meeting Transcript</DialogTitle>
        </DialogHeader>

        {transcriptQuery.isPending && (
          <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
            Loading transcript...
          </div>
        )}

        {transcriptQuery.isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {transcriptQuery.error instanceof Error
              ? transcriptQuery.error.message
              : 'Failed to load meeting transcript.'}
          </div>
        )}

        {transcript && (
          <div className="flex min-h-0 flex-1 flex-col gap-4">
            <div className="rounded-lg border bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold text-slate-900">{transcript.meeting_id}</h3>
                <Badge variant="outline">Transcript</Badge>
                <Badge variant="secondary">Requirement: {transcript.requirement_id}</Badge>
                {transcript.project_id && (
                  <Badge variant="secondary">Project: {transcript.project_id}</Badge>
                )}
              </div>
              {transcript.updated_at && (
                <p className="mt-2 text-sm text-slate-600">
                  Updated: {formatTimestamp(transcript.updated_at)}
                </p>
              )}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto rounded-lg border bg-slate-100/70 p-4">
              {transcriptEntries.length > 0 ? (
                <div className="flex flex-col gap-4">
                  {transcriptEntries.map((entry, index) => {
                    const title = getEntryTitle(entry)
                    const body = getEntryBody(entry)
                    const timestamp = formatTimestamp(entry.created_at)
                    const rawPrompt = entry.raw_prompt || entry.prompt
                    const rawReply = entry.raw_reply || entry.reply

                    return (
                      <article
                        key={entry.id || `${title}-${index}`}
                        className={`max-w-[85%] px-4 py-3 shadow-sm ${getRoleTone(entry)}`}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold text-slate-900">{title}</span>
                          {(entry.role || entry.agent_role || entry.speaker) && (
                            <Badge variant="outline" className="capitalize">
                              {entry.role || entry.agent_role || entry.speaker}
                            </Badge>
                          )}
                          {entry.node_name && (
                            <Badge variant="secondary">{entry.node_name}</Badge>
                          )}
                          {timestamp && (
                            <span className="text-xs text-slate-500">{timestamp}</span>
                          )}
                        </div>
                        <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">
                          {body}
                        </p>

                        {(rawPrompt || rawReply) && (
                          <details className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
                            <summary className="cursor-pointer text-sm font-medium text-slate-700">
                              Raw prompt and reply
                            </summary>
                            <div className="mt-3 space-y-3 text-xs text-slate-600">
                              {rawPrompt && (
                                <div>
                                  <p className="font-semibold uppercase tracking-wide text-slate-500">
                                    Prompt
                                  </p>
                                  <pre className="mt-1 whitespace-pre-wrap break-words rounded border bg-white p-3 font-mono">
                                    {rawPrompt}
                                  </pre>
                                </div>
                              )}
                              {rawReply && (
                                <div>
                                  <p className="font-semibold uppercase tracking-wide text-slate-500">
                                    Reply
                                  </p>
                                  <pre className="mt-1 whitespace-pre-wrap break-words rounded border bg-white p-3 font-mono">
                                    {rawReply}
                                  </pre>
                                </div>
                              )}
                              {entry.context && (
                                <div>
                                  <p className="font-semibold uppercase tracking-wide text-slate-500">
                                    Context
                                  </p>
                                  <pre className="mt-1 whitespace-pre-wrap break-words rounded border bg-white p-3 font-mono">
                                    {JSON.stringify(entry.context, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          </details>
                        )}
                      </article>
                    )
                  })}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed bg-white p-6 text-sm text-slate-600">
                  No structured transcript entries were returned for this meeting yet. The meeting
                  summary and minutes are still available through the existing meeting endpoint.
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
