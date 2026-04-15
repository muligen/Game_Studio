import { useWorkspace } from '@/lib/workspace'
import { logsApi } from '@/lib/api'
import { useQuery } from '@tanstack/react-query'

export function Logs() {
  const { workspace } = useWorkspace()

  const { data: logs, isLoading } = useQuery({
    queryKey: ['logs', workspace],
    queryFn: () => logsApi.list(workspace, 100),
  })

  if (isLoading) {
    return <div>Loading...</div>
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Logs</h1>

      <div className="space-y-2">
        {logs?.map((log: any) => (
          <div key={log.id} className="p-4 border rounded-lg bg-card">
            <div className="flex justify-between items-start mb-2">
              <div className="flex gap-4 text-sm text-muted-foreground">
                <span>{new Date(log.timestamp).toLocaleString()}</span>
                <span className="font-medium">{log.actor}</span>
                <span className="text-blue-600">{log.action}</span>
              </div>
              <span className="text-xs text-muted-foreground">{log.id}</span>
            </div>
            <p>{log.message}</p>
            {log.target_type && (
              <span className="text-xs text-muted-foreground">
                {log.target_type}:{log.target_id}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
