import { KanbanColumn } from './KanbanColumn'

interface Requirement {
  id: string
  title: string
  status?: string
  priority?: string
  design_doc_id?: string | null
}

interface KanbanBoardProps {
  requirements: Requirement[]
  onCardClick: (id: string) => void
  workspace: string
}

const COLUMNS = [
  { key: 'draft', title: 'Draft' },
  { key: 'designing', title: 'Designing' },
  { key: 'pending_user_review', title: 'Pending Review' },
  { key: 'approved', title: 'Approved' },
  { key: 'implementing', title: 'Implementing' },
  { key: 'self_test_passed', title: 'Self Test Passed' },
  { key: 'testing', title: 'Testing' },
  { key: 'pending_user_acceptance', title: 'Pending Acceptance' },
  { key: 'quality_check', title: 'Quality Check' },
  { key: 'done', title: 'Done' },
]

export function KanbanBoard({ requirements, onCardClick, workspace }: KanbanBoardProps) {
  const groupedRequirements = COLUMNS.map((column) => ({
    ...column,
    requirements: requirements.filter((req) => req.status === column.key),
  }))

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {groupedRequirements.map((column) => (
        <KanbanColumn
          key={column.key}
          title={column.title}
          requirements={column.requirements}
          onCardClick={onCardClick}
          workspace={workspace}
        />
      ))}
    </div>
  )
}
