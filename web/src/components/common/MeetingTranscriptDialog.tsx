import { useQuery } from '@tanstack/react-query'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { meetingsApi, type MeetingDetails, type MeetingTranscriptEntry } from '@/lib/api'

interface MeetingTranscriptDialogProps {
  workspace: string
  meetingId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function getTranscriptEntries(meeting: MeetingDetails | undefined): MeetingTranscriptEntry[] {
  if (!meeting) return []

  const candidates = [meeting.transcript, meeting.transcript_entries, meeting.raw_transcript]
  for (const candidate of candidates) {
    if (candidate && candidate.length > 0) {
      return candidate
    }
  }

  return []
}

function getEntryTitle(entry: MeetingTranscriptEntry): string {
  return entry.label || entry.speaker || entry.agent_role || entry.role || 'Transcript Entry'
}

function getEntryBody(entry: MeetingTranscriptEntry): string {
  return entry.content || entry.summary || entry.reply || entry.raw_reply || 'No transcript text recorded.'
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
  const meetingQuery = useQuery({
    queryKey: ['meeting-transcript', workspace, meetingId],
    queryFn: () => meetingsApi.get(workspace, meetingId!),
    enabled: open && Boolean(meetingId),
  })

  const transcriptEntries = getTranscriptEntries(meetingQuery.data)
  const attendees = meetingQuery.data?.attendees ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] max-w-5xl flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>Meeting Transcript</DialogTitle>
        </DialogHeader>

        {meetingQuery.isPending && (
          <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
            Loading transcript...
          </div>
        )}

        {meetingQuery.isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {meetingQuery.error instanceof Error
              ? meetingQuery.error.message
              : 'Failed to load meeting transcript.'}
          </div>
        )}

        {meetingQuery.data && (
          <div className="flex min-h-0 flex-1 flex-col gap-4">
            <div className="rounded-lg border bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold text-slate-900">{meetingQuery.data.title}</h3>
                <Badge variant="outline">{meetingQuery.data.status ?? 'unknown'}</Badge>
                <Badge variant="secondary">Meeting ID: {meetingQuery.data.id}</Badge>
              </div>
              <p className="mt-2 text-sm text-slate-600">
                Requirement: {meetingQuery.data.requirement_id}
              </p>
              {attendees.length > 0 && (
                <p className="mt-2 text-sm text-slate-600">
                  Attendees: {attendees.join(', ')}
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
                          {entry.role && (
                            <Badge variant="outline" className="capitalize">
                              {entry.role}
                            </Badge>
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
