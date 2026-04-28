import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import type { BaselineStatus } from '@/lib/product-workbench'

interface ProductWorkbenchHeaderProps {
  baselineStatus: BaselineStatus
  onCreateRequirement: () => void
  onContinueClarifying?: () => void
  hasActiveIteration: boolean
}

const STATUS_CONFIG: Record<
  BaselineStatus,
  { title: string; description: string; actionLabel: string; icon: string; cardClass: string }
> = {
  not_started: {
    title: 'No product baseline yet',
    description: 'Create the first requirement to define the MVP.',
    actionLabel: 'Create MVP Requirement',
    icon: '🛠️',
    cardClass: 'bg-gradient-to-r from-gray-50 to-gray-100 border-gray-200',
  },
  defining_mvp: {
    title: 'MVP definition in progress',
    description: 'Clarify the product goal, MVP scope, constraints, and acceptance criteria before kickoff.',
    actionLabel: 'Continue Clarifying MVP',
    icon: '📝',
    cardClass: 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200',
  },
  active: {
    title: 'Product baseline active',
    description: 'Create change requests to iterate on the product.',
    actionLabel: 'Add Change Request',
    icon: '✅',
    cardClass: 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200',
  },
}

export function ProductWorkbenchHeader({
  baselineStatus,
  onCreateRequirement,
  onContinueClarifying,
  hasActiveIteration,
}: ProductWorkbenchHeaderProps) {
  const config = STATUS_CONFIG[baselineStatus]

  return (
    <Card className={`p-6 border ${config.cardClass}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-2xl">{config.icon}</span>
            <h2 className="text-xl font-semibold text-gray-900">{config.title}</h2>
          </div>
          <p className="text-gray-600 text-sm">
            {config.description}
            {hasActiveIteration && baselineStatus === 'active' && (
              <span className="ml-1 text-amber-600 font-medium">An active iteration is in progress.</span>
            )}
            {!hasActiveIteration && baselineStatus === 'active' && (
              <span className="ml-1 text-green-600">All iterations complete.</span>
            )}
          </p>
        </div>

        {baselineStatus === 'defining_mvp' && onContinueClarifying ? (
          <Button onClick={onContinueClarifying} className="ml-4">
            {config.actionLabel}
          </Button>
        ) : (
          <Button onClick={onCreateRequirement} className="ml-4">
            {config.actionLabel}
          </Button>
        )}
      </div>
    </Card>
  )
}
