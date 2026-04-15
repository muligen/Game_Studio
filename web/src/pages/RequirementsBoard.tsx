import { useQuery } from '@tanstack/react-query'
import { KanbanBoard } from '@/components/board/KanbanBoard'
import { Button } from '@/components/ui/button'
import { requirementsApi } from '@/lib/api'

const WORKSPACE = 'default'

export function RequirementsBoard() {
  const { data: requirements, isLoading, error } = useQuery({
    queryKey: ['requirements', WORKSPACE],
    queryFn: () => requirementsApi.list(WORKSPACE),
  })

  const handleCardClick = (id: string) => {
    console.log('Clicked requirement:', id)
    alert(`Requirement detail view for "${id}" is coming soon!\n\nThis will navigate to the requirement detail page in the next iteration.`)
    // TODO: Navigate to requirement detail page
  }

  const handleCreate = () => {
    console.log('Create new requirement')
    alert('Create Requirement form is coming soon!\n\nThis will open a dialog to create new requirements in the next iteration.')
    // TODO: Open create requirement dialog
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">Loading requirements...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-red-600">Error loading requirements: {error.message}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900">Requirements Board</h1>
          <Button onClick={handleCreate}>Create Requirement</Button>
        </div>

        {requirements && requirements.length > 0 ? (
          <KanbanBoard requirements={requirements} onCardClick={handleCardClick} />
        ) : (
          <div className="bg-white rounded-lg shadow-md p-8 text-center">
            <p className="text-gray-600 mb-4">No requirements found</p>
            <Button onClick={handleCreate}>Create First Requirement</Button>
          </div>
        )}
      </div>
    </div>
  )
}
