import { useQuery } from '@tanstack/react-query'
import { useWorkspace } from '@/lib/workspace'
import { bugsApi } from '@/lib/api'

const BUG_COLUMNS = [
  { status: 'new', title: 'New' },
  { status: 'fixing', title: 'Fixing' },
  { status: 'fixed', title: 'Fixed' },
  { status: 'verifying', title: 'Verifying' },
  { status: 'reopened', title: 'Reopened' },
  { status: 'needs_user_decision', title: 'Needs Decision' },
  { status: 'closed', title: 'Closed' },
]

export function BugsBoard() {
  const { workspace } = useWorkspace()

  const { data: bugs, isLoading, error } = useQuery({
    queryKey: ['bugs', workspace],
    queryFn: () => bugsApi.list(workspace),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">Loading bugs...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-red-600">Error loading bugs: {error.message}</p>
      </div>
    )
  }

  const grouped = BUG_COLUMNS.map((col) => ({
    ...col,
    cards: bugs?.filter((b: any) => b.status === col.status) || [],
  }))

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8 space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900">Bugs</h1>
        </div>
        <div className="flex gap-6 overflow-x-auto pb-4">
          {grouped.map((col) => (
            <div key={col.status} className="flex-shrink-0 w-80">
              <h2 className="font-semibold mb-4 text-sm uppercase text-gray-600">
                {col.title} ({col.cards.length})
              </h2>
              <div className="space-y-3">
                {col.cards.map((bug: any) => (
                  <div
                    key={bug.id}
                    className="p-4 border rounded-lg bg-white shadow-sm hover:shadow-md transition-shadow"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-xs text-gray-500">{bug.id}</span>
                      <span className={`text-xs px-2 py-1 rounded ${
                        bug.reopen_count >= 3 ? 'bg-red-200 text-red-800' : 'bg-gray-200 text-gray-700'
                      }`}>
                        ↻ {bug.reopen_count || 0}
                      </span>
                    </div>
                    <h3 className="font-medium text-gray-900 mb-2">{bug.title}</h3>
                    <span className={`text-xs px-2 py-1 rounded inline-block ${
                      bug.severity === 'critical' ? 'bg-red-500 text-white' :
                      bug.severity === 'high' ? 'bg-orange-500 text-white' :
                      bug.severity === 'medium' ? 'bg-yellow-500 text-white' :
                      'bg-gray-400 text-white'
                    }`}>
                      {bug.severity || 'unknown'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
