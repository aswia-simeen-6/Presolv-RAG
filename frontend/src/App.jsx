import { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'

const API = import.meta.env.VITE_API_URL || '/api'

let msgCounter = 0
const uid = () => ++msgCounter

export default function App() {
  const [documents, setDocuments] = useState([])
  const [indexed,   setIndexed]   = useState(false)
  const [messages,  setMessages]  = useState([])
  const [isLoading, setIsLoading] = useState(false)

  const refreshDocs = useCallback(() => {
    fetch(`${API}/documents`)
      .then(r => r.json())
      .then(data => {
        setDocuments(data.documents || [])
        setIndexed(data.indexed !== false)
      })
      .catch(() => {})

    fetch(`${API}/health`)
      .then(r => r.json())
      .then(data => setIndexed(data.indexed === true))
      .catch(() => {})
  }, [])

  // Load document list on mount
  useEffect(() => { refreshDocs() }, [refreshDocs])

  // Update a message in state by id
  const updateMsg = useCallback((id, patch) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, ...patch } : m))
  }, [])

  const handleSubmit = useCallback(async (question) => {
    if (isLoading) return
    setIsLoading(true)

    // Add user message
    const userMsgId = uid()
    setMessages(prev => [...prev, { id: userMsgId, role: 'user', content: question }])

    // Add thinking placeholder
    const assistantMsgId = uid()
    setMessages(prev => [...prev, {
      id:       assistantMsgId,
      role:     'thinking',
      content:  '',
      sources:  [],
      citations:[],
    }])

    try {
      const response = await fetch(`${API}/query/stream`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ question }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader  = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      // Transition from thinking → streaming assistant
      updateMsg(assistantMsgId, { role: 'assistant', streaming: true })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Process complete SSE lines
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''   // last incomplete line stays in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let event
          try { event = JSON.parse(line.slice(6)) }
          catch { continue }

          switch (event.type) {
            case 'sources':
              updateMsg(assistantMsgId, { sources: event.sources })
              break

            case 'token':
              setMessages(prev => prev.map(m =>
                m.id === assistantMsgId
                  ? { ...m, content: (m.content || '') + event.content }
                  : m
              ))
              break

            case 'citations':
              updateMsg(assistantMsgId, { citations: event.citations })
              break

            case 'refused':
              updateMsg(assistantMsgId, {
                role:     'assistant',
                refused:  true,
                streaming:false,
                content:  event.message,
                sources:  [],
              })
              break

            case 'error':
              updateMsg(assistantMsgId, {
                role:     'assistant',
                error:    true,
                streaming:false,
                content:  event.message,
              })
              break

            case 'done':
              updateMsg(assistantMsgId, { streaming: false })
              break

            default:
              break
          }
        }
      }

      // Ensure streaming cursor is removed on stream end
      updateMsg(assistantMsgId, { streaming: false })

    } catch (err) {
      updateMsg(assistantMsgId, {
        role:     'assistant',
        error:    true,
        streaming:false,
        content:  `Connection error: ${err.message}`,
      })
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, updateMsg])

  return (
    <div className="flex h-screen bg-slate-100">
      <Sidebar documents={documents} indexed={indexed} onUpload={refreshDocs} />
      <main className="flex-1 flex flex-col min-w-0 bg-slate-50">
        {/* Top bar */}
        <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between flex-shrink-0">
          <div>
            <h1 className="font-semibold text-slate-800 text-base">Document Q&A</h1>
            <p className="text-xs text-slate-400">
              {documents.length} document{documents.length !== 1 ? 's' : ''} indexed
            </p>
          </div>
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="text-xs text-slate-400 hover:text-red-500 transition-colors px-2 py-1 rounded"
            >
              Clear chat
            </button>
          )}
        </header>

        <ChatArea
          messages={messages}
          isLoading={isLoading}
          onSubmit={handleSubmit}
          documents={documents}
        />
      </main>
    </div>
  )
}
