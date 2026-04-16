import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { useWorkspace } from '@/lib/workspace'
import { designDocsApi } from '@/lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import type { DesignDoc } from '@/lib/custom-types'

function EditableList({ items, onChange, disabled }: {
  items: string[]
  onChange: (items: string[]) => void
  disabled: boolean
}) {
  const [text, setText] = useState(items.join('\n'))

  useEffect(() => {
    setText(items.join('\n'))
  }, [items])

  return (
    <textarea
      className="w-full min-h-[80px] p-2 border rounded text-sm font-mono"
      value={text}
      onChange={(e) => {
        setText(e.target.value)
        onChange(e.target.value.split('\n').filter(Boolean))
      }}
      disabled={disabled}
    />
  )
}

export function DesignEditor() {
  const { id } = useParams<{ id: string }>()
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()
  const [sendBackOpen, setSendBackOpen] = useState(false)
  const [sendBackReason, setSendBackReason] = useState('')
  const [editedFields, setEditedFields] = useState<{
    core_rules: string[]
    acceptance_criteria: string[]
    open_questions: string[]
  }>({ core_rules: [], acceptance_criteria: [], open_questions: [] })
  const [hasEdits, setHasEdits] = useState(false)

  const { data: design, isLoading } = useQuery({
    queryKey: ['design-doc', id, workspace],
    queryFn: () => designDocsApi.get(workspace, id!) as Promise<DesignDoc>,
    enabled: !!id,
  })

  const saveMutation = useMutation({
    mutationFn: (data: Partial<DesignDoc>) => designDocsApi.update(workspace, id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['design-doc'] })
      setHasEdits(false)
    },
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
      setSendBackOpen(false)
      setSendBackReason('')
    },
  })

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground">Loading...</div>
  }

  if (!design) {
    return <div className="p-8 text-center text-muted-foreground">Design doc not found</div>
  }

  const isEditable = design.status === 'pending_user_review'

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">{design.title}</h1>
          <p className="text-muted-foreground">{id}</p>
        </div>
        <Badge>{design.status}</Badge>
      </div>

      {design.sent_back_reason && (
        <Card className="border-orange-300 bg-orange-50">
          <CardHeader>
            <CardTitle className="text-orange-800">Sent Back Reason</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-orange-900">{design.sent_back_reason}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p>{design.summary}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Core Rules</CardTitle>
        </CardHeader>
        <CardContent>
          <EditableList
            items={design.core_rules || []}
            onChange={(items) => {
              setEditedFields((prev) => ({ ...prev, core_rules: items }))
              setHasEdits(true)
            }}
            disabled={!isEditable}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Acceptance Criteria</CardTitle>
        </CardHeader>
        <CardContent>
          <EditableList
            items={design.acceptance_criteria || []}
            onChange={(items) => {
              setEditedFields((prev) => ({ ...prev, acceptance_criteria: items }))
              setHasEdits(true)
            }}
            disabled={!isEditable}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Open Questions</CardTitle>
        </CardHeader>
        <CardContent>
          <EditableList
            items={design.open_questions || []}
            onChange={(items) => {
              setEditedFields((prev) => ({ ...prev, open_questions: items }))
              setHasEdits(true)
            }}
            disabled={!isEditable}
          />
        </CardContent>
      </Card>

      <div className="flex gap-4">
        {isEditable && (
          <>
            <Button
              onClick={() => saveMutation.mutate(editedFields)}
              disabled={!hasEdits || saveMutation.isPending}
            >
              {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
            <Button
              onClick={() => approveMutation.mutate()}
              disabled={approveMutation.isPending}
            >
              ✓ Approve
            </Button>
            <Button
              variant="outline"
              onClick={() => setSendBackOpen(true)}
              disabled={sendBackMutation.isPending}
            >
              ⏪ Send Back
            </Button>
          </>
        )}
      </div>

      <Dialog open={sendBackOpen} onOpenChange={setSendBackOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send Back for Revision</DialogTitle>
          </DialogHeader>
          <textarea
            className="w-full min-h-[120px] p-3 border rounded"
            placeholder="Describe what needs to be changed..."
            value={sendBackReason}
            onChange={(e) => setSendBackReason(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setSendBackOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (sendBackReason.trim()) {
                  sendBackMutation.mutate(sendBackReason.trim())
                }
              }}
              disabled={!sendBackReason.trim() || sendBackMutation.isPending}
            >
              {sendBackMutation.isPending ? 'Sending...' : 'Send Back'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
