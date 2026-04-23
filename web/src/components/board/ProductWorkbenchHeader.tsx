import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import type { BaselineStatus } from '@/lib/product-workbench'

interface ProductWorkbenchHeaderProps {
  baselineStatus: BaselineStatus
  onCreateRequirement: () => void
  onContinueClarifying?: () => void
  mvpRequirementId?: string | null
  latestMeetingId?: string | null
}

const STATUS_CONFIG: Record<BaselineStatus, {
  title: string
  description: string
  actionLabel: string
  actionKind: 'create' | 'clarify'
  icon: string
  cardClass: string
}> = {
  not_started: {
    title: 'No product baseline yet',
    description: 'Create and clarify the first requirement to define the MVP.',
    actionLabel: 'Create MVP Requirement',
    actionKind: 'create',
    icon: '\uD83D\uDEE0\uFE0F',
    cardClass: 'bg-gradient-to-r from-gray-50 to-gray-100 border-gray-200',
  },
  defining_mvp: {
    title: 'MVP definition in progress',
    description: 'Clarify the product goal, MVP scope, constraints, and acceptance criteria before kickoff.',
    actionLabel: 'Continue Clarifying MVP',
    actionKind: 'clarify',
    icon: '\uD83D\uDCDD',
    cardClass: 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200',
  },
  active: {
    title: 'Product baseline active',
    description: 'New requirements are treated as change requests against the current product.',
    actionLabel: 'Add Change Request',
    actionKind: 'create',
    icon: '\u2705',
    cardClass: 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200',
  },
}

export function ProductWorkbenchHeader({
  baselineStatus,
  onCreateRequirement,
  onContinueClarifying,
  mvpRequirementId,
  latestMeetingId,
}: ProductWorkbenchHeaderProps) {
  const config = STATUS_CONFIG[baselineStatus]

  const handleAction = () => {
    if (config.actionKind === 'clarify' && onContinueClarifying) {
      onContinueClarifying()
    } else {
      onCreateRequirement()
    }
  }

  return (
    <Card className={`p-6 border ${config.cardClass}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-2xl">{config.icon}</span>
            <h2 className="text-xl font-semibold text-gray-900">{config.title}</h2>
          </div>
          <p className="text-gray-600 text-sm mb-3">{config.description}</p>

          {baselineStatus === 'active' && (
            <div className="flex gap-4 text-xs text-muted-foreground">
              {mvpRequirementId && (
                <span>MVP: {mvpRequirementId}</span>
              )}
              {latestMeetingId && (
                <span>Latest meeting: {latestMeetingId}</span>
              )}
            </div>
          )}

          {baselineStatus === 'active' && !latestMeetingId && (
            <div className="mt-2 text-xs text-muted-foreground italic">
              The product baseline will appear here after the MVP kickoff meeting.
            </div>
          )}
        </div>

        <Button onClick={handleAction} className="ml-4">
          {config.actionLabel}
        </Button>
      </div>
    </Card>
  )
}
