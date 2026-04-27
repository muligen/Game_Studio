import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { agentsApi, poolApi, type AgentMessage } from '@/lib/api'
import { useWorkspace } from '@/lib/workspace'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export function AgentChat() {
  const { workspace } = useWorkspace()
  const { projectId, agent } = useParams<{ projectId: string; agent: string }>()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')

  const { data: pool } = useQuery({
    queryKey: ['pool-status'],
    queryFn: () => poolApi.status(),
    refetchInterval: 5000,
  })

  const historyQuery = useQuery({
    queryKey: ['agent-messages', projectId, agent],
    queryFn: () => agentsApi.getMessages(projectId!, agent!, workspace),
    enabled: !!projectId && !!agent,
  })

  useEffect(() => {
    if (historyQuery.data?.messages) {
      setMessages(
        historyQuery.data.messages.map((m: AgentMessage) => ({
          role: m.role,
          content: m.content,
        })),
      )
    }
  }, [historyQuery.data])

  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      agentsApi.chat(projectId!, agent!, { message }, workspace),
    onSuccess: (data) => {
      setMessages(prev => [...prev, { role: 'assistant', content: data.content }])
    },
    onError: (error: Error) => {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `[Error] ${error.message}` },
      ])
    },
  })

  const isRunning = (pool?.tasks as Array<{ agent_type: string }>)?.some(
    t => t.agent_type === agent,
  )

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || isRunning || chatMutation.isPending) return

    setMessages(prev => [...prev, { role: 'user', content: trimmed }])
    chatMutation.mutate(trimmed)
    setInput('')
  }

  if (!projectId || !agent) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <p className="text-gray-600">Invalid agent URL</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      <div className="bg-white border-b px-4 py-3">
        <div className="container mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/agents" className="text-sm text-blue-600 hover:underline">
              &larr; Agents
            </Link>
            <h1 className="text-xl font-bold capitalize">{agent}</h1>
            <span className="text-sm text-gray-500 font-mono">{projectId}</span>
          </div>
          <span
            className={`text-sm px-3 py-1 rounded ${
              isRunning ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
            }`}
          >
            {isRunning ? 'Busy' : 'Idle'}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto container mx-auto px-4 py-4">
        <div className="max-w-2xl mx-auto space-y-3">
          {historyQuery.isLoading ? (
            <div className="text-center text-gray-400 mt-12">
              <p className="text-lg">Loading history...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="text-center text-gray-400 mt-12">
              <p className="text-lg">Chat with {agent} agent</p>
              <p className="text-sm mt-1">Messages are sent using the agent's Claude session</p>
            </div>
          ) : null}
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[80%] px-4 py-2 rounded-lg ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white border shadow-sm text-gray-800'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}
          {chatMutation.isPending && (
            <div className="flex justify-start">
              <div className="bg-white border shadow-sm text-gray-500 px-4 py-2 rounded-lg">
                Agent is thinking...
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white border-t px-4 py-3">
        <div className="container mx-auto max-w-2xl flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            disabled={isRunning || chatMutation.isPending}
            className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:bg-gray-100 disabled:cursor-not-allowed"
            placeholder={isRunning ? 'Agent is busy...' : 'Type a message...'}
          />
          <button
            onClick={handleSend}
            disabled={isRunning || chatMutation.isPending || !input.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
