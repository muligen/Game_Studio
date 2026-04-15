import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useWorkspace } from '@/lib/workspace'
import { designDocsApi } from '@/lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

export function DesignEditor() {
  const { id } = useParams<{ id: string }>()
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()

  const { data: design, isLoading } = useQuery({
    queryKey: ['design-doc', id, workspace],
    queryFn: () => designDocsApi.get(workspace, id!),
    enabled: !!id,
  })

  const approveMutation = useMutation({
    mutationFn: () => designDocsApi.approve(workspace, id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['design-doc'] })
      queryClient.invalidateQueries({ queryKey: ['requirements'] })
    },
  })

  const sendBackMutation = useMutation({
    mutationFn: (reason: string) => designDocsApi.sendBack(workspace, id!, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['design-doc'] })
      queryClient.invalidateQueries({ queryKey: ['requirements'] })
    },
  })

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground">Loading...</div>
  }

  if (!design) {
    return <div className="p-8 text-center text-muted-foreground">Design doc not found</div>
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">{(design as any).title}</h1>
          <p className="text-muted-foreground">{id}</p>
        </div>
        <Badge>{(design as any).status}</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p>{(design as any).summary}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Core Rules</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc pl-6 space-y-2">
            {(design as any).core_rules?.map((rule: string, i: number) => (
              <li key={i}>{rule}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Acceptance Criteria</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc pl-6 space-y-2">
            {(design as any).acceptance_criteria?.map((criterion: string, i: number) => (
              <li key={i}>{criterion}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Open Questions</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc pl-6 space-y-2">
            {(design as any).open_questions?.map((question: string, i: number) => (
              <li key={i}>{question}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="flex gap-4">
        <Button
          onClick={() => approveMutation.mutate()}
          disabled={(design as any).status !== 'pending_user_review'}
        >
          ✓ Approve
        </Button>
        <Button
          variant="outline"
          onClick={() => {
            const reason = prompt('Reason for sending back:')
            if (reason) sendBackMutation.mutate(reason)
          }}
          disabled={(design as any).status !== 'pending_user_review'}
        >
          ⏪ Send Back
        </Button>
      </div>
    </div>
  )
}
