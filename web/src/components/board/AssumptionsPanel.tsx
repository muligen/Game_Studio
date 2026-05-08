import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { NeedsAttentionItem, ProjectAssumption } from '@/lib/api'

interface AssumptionsPanelProps {
  assumptions: ProjectAssumption[]
  needsAttentionItems: NeedsAttentionItem[]
}

export function AssumptionsPanel({ assumptions, needsAttentionItems }: AssumptionsPanelProps) {
  const openNeedsAttention = needsAttentionItems.filter((item) => item.status === 'open')

  if (assumptions.length === 0 && openNeedsAttention.length === 0) {
    return null
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {openNeedsAttention.length > 0 && (
        <Card className="p-4 border-red-300 bg-red-50">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold text-red-900">Needs Attention</h2>
            <Badge className="bg-red-200 text-red-900">{openNeedsAttention.length}</Badge>
          </div>
          <div className="mt-3 space-y-3">
            {openNeedsAttention.map((item) => (
              <div key={item.id} className="text-sm">
                <p className="font-medium text-red-950">{item.blocker}</p>
                <p className="text-red-800">{item.recommended_action}</p>
                {item.evidence.length > 0 && (
                  <ul className="mt-1 list-disc pl-5 text-red-700">
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
