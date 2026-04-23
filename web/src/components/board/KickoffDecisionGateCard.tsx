import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { KickoffDecisionGate } from '@/lib/api'

interface KickoffDecisionGateCardProps {
  gate: KickoffDecisionGate
  onResolve?: () => void
}

export function KickoffDecisionGateCard({ gate, onResolve }: KickoffDecisionGateCardProps) {
  const isOpen = gate.status === 'open'

  return (
    <Card className="p-4 border-amber-300 bg-amber-50">
      <div className="flex justify-between items-start mb-2">
        <Badge className={isOpen ? 'bg-amber-200 text-amber-800' : 'bg-green-200 text-green-800'}>
          {isOpen ? 'Kickoff Decision Required' : 'Resolved'}
        </Badge>
        <span className="text-xs text-muted-foreground">{gate.id}</span>
      </div>
      <h3 className="font-medium mb-3">Decision Gate</h3>
      <div className="space-y-3">
        {gate.items.map((item) => (
          <div key={item.id} className="text-sm">
            <p className="font-medium">{item.question}</p>
            <p className="text-muted-foreground text-xs">{item.context}</p>
            {item.resolution ? (
              <p className="text-green-700 text-xs mt-1">Resolved: {item.resolution}</p>
            ) : (
              <div className="flex gap-1 mt-1 flex-wrap">
                {item.options.map((opt) => (
                  <Badge key={opt} variant="outline" className="text-xs">{opt}</Badge>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {isOpen && onResolve && (
        <button
          className="mt-3 w-full text-sm font-medium text-amber-800 hover:underline"
          onClick={onResolve}
        >
          Resolve Decisions
        </button>
      )}
    </Card>
  )
}
