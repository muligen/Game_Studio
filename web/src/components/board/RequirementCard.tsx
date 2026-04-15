import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface RequirementCardProps {
  id: string
  title: string
  status?: string
  priority?: string
  onClick: () => void
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  designing: 'bg-blue-100 text-blue-800',
  pending_user_review: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  implementing: 'bg-purple-100 text-purple-800',
  testing: 'bg-orange-100 text-orange-800',
  done: 'bg-emerald-100 text-emerald-800',
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-gray-200',
  medium: 'bg-yellow-200',
  high: 'bg-red-200',
}

export function RequirementCard({ id, title, status, priority, onClick }: RequirementCardProps) {
  const statusValue = status || 'draft'
  const priorityValue = priority || 'medium'

  return (
    <Card
      className="p-4 cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs text-muted-foreground">{id}</span>
        <Badge className={PRIORITY_COLORS[priorityValue]}>{priorityValue}</Badge>
      </div>
      <h3 className="font-medium mb-2">{title}</h3>
      <Badge className={STATUS_COLORS[statusValue] || STATUS_COLORS.draft}>
        {statusValue.replace(/_/g, ' ')}
      </Badge>
    </Card>
  )
}
