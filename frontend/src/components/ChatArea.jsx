import { useEffect, useRef } from 'react'
import Message from './Message'
import InputBar from './InputBar'

function WelcomeScreen({ documents }) {
  const examples = [
    'What are the key findings in these documents?',
    'Summarize the main policies described.',
    'What are the FAQs about this topic?',
  ]

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-8">
      <div className="text-5xl mb-4">🔍</div>
      <h2 className="text-2xl font-bold text-slate-800 mb-2">Ask your documents anything</h2>
      <p className="text-slate-500 text-sm max-w-md mb-8">
        I'll search across {documents.length > 0 ? `all ${documents.length} documents` : 'your documents'} and cite exactly where the answer comes from.
      </p>

      {examples.length > 0 && (
        <div className="space-y-2 w-full max-w-md">
          <p className="text-xs text-slate-400 font-semibold uppercase tracking-widest mb-3">Try asking</p>
          {examples.map((ex, i) => (
            <div key={i}
                 className="bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-600 cursor-default hover:border-indigo-300 hover:text-indigo-700 transition-colors text-left shadow-sm">
              {ex}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ChatArea({ messages, isLoading, onSubmit, documents }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 ? (
          <WelcomeScreen documents={documents} />
        ) : (
          <div className="max-w-3xl mx-auto">
            {messages.map(msg => (
              <Message key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <InputBar onSubmit={onSubmit} disabled={isLoading} />
    </div>
  )
}
