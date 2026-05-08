import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { NeedsAttentionItem, ProjectAssumption } from '@/lib/api'

type RunnerStatus =
  | 'idle'
  | 'running'
  | 'waiting_for_decision'
  | 'validating'
  | 'repairing'
  | 'accepted'
  | 'needs_attention'
  | 'failed'
  | 'completed'

interface AssumptionsPanelProps {
  assumptions: ProjectAssumption[]
  needsAttentionItems: NeedsAttentionItem[]
  runnerStatus?: RunnerStatus
}

export function AssumptionsPanel({ assumptions, needsAttentionItems, runnerStatus }: AssumptionsPanelProps) {
  const openNeedsAttention = needsAttentionItems.filter((item) => item.status === 'open')
  const isBlocking = runnerStatus === 'needs_attention' || runnerStatus === 'failed' || runnerStatus === 'waiting_for_decision'
  const attentionTone = isBlocking
    ? {
        card: 'border-red-300 bg-red-50',
        heading: 'text-red-900',
        badge: 'bg-red-200 text-red-900',
        title: 'Needs Attention',
        blocker: 'text-red-950',
        action: 'text-red-800',
        evidence: 'text-red-700',
      }
    : {
        card: 'border-amber-200 bg-amber-50',
        heading: 'text-amber-900',
        badge: 'bg-amber-100 text-amber-900',
        title: 'Repair Watchlist',
        blocker: 'text-amber-950',
        action: 'text-amber-800',
        evidence: 'text-amber-700',
      }

  if (assumptions.length === 0 && openNeedsAttention.length === 0) {
    return null
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {openNeedsAttention.length > 0 && (
        <Card className={`p-4 ${attentionTone.card}`}>
          <div className="flex items-center justify-between gap-3">
            <h2 className={`font-semibold ${attentionTone.heading}`}>{attentionTone.title}</h2>
            <Badge className={attentionTone.badge}>{openNeedsAttention.length}</Badge>
          </div>
          {!isBlocking && (
            <p className="mt-2 text-sm text-amber-800">
              Delivery is continuing automatically; these items are being tracked for the repair loop.
            </p>
          )}
          <div className="mt-3 space-y-3">
            {openNeedsAttention.map((item) => (
              <div key={item.id} className="text-sm">
                <p className={`font-medium ${attentionTone.blocker}`}>{item.blocker}</p>
                <p className={attentionTone.action}>{item.recommended_action}</p>
                {item.evidence.length > 0 && (
                  <ul className={`mt-1 list-disc pl-5 ${attentionTone.evidence}`}>
                    {item.evidence.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
      {assumptions.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold">Assumptions & Decisions</h2>
            <Badge variant="secondary">{assumptions.length}</Badge>
          </div>
          <div className="mt-3 grid gap-3">
            {assumptions.map((assumption) => (
              <div key={assumption.id} className="rounded-md border p-3 text-sm">
                <div className="mb-1 flex items-center gap-2">
                  <Badge variant="outline">{assumption.category}</Badge>
                  <span className="text-xs text-muted-foreground">{assumption.owner_agent}</span>
                </div>
                <p className="font-medium">{assumption.decision}</p>
                <p className="mt-1 text-muted-foreground">{assumption.rationale}</p>
                <p className="mt-1 text-xs text-muted-foreground">{assumption.impact}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
