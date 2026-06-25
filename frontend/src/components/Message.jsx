import { useState } from 'react'
import SourceCard from './SourceCard'

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5 px-4 py-3">
      {[0, 150, 300].map(delay => (
        <div
          key={delay}
          className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  )
}

export default function Message({ message }) {
  const [sourcesOpen, setSourcesOpen] = useState(false)

  if (message.role === 'user') {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-xl bg-indigo-600 text-white px-4 py-3 rounded-2xl rounded-tr-sm text-sm leading-relaxed shadow-sm">
          {message.content}
        </div>
      </div>
    )
  }

  if (message.role === 'thinking') {
    return (
      <div className="flex justify-start mb-4">
        <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm">
          <ThinkingDots />
        </div>
      </div>
    )
  }

  // Assistant message
  const isRefused = message.refused
  const isError   = message.error
  const isStreaming = message.streaming

  const bubbleClass = isRefused
    ? 'bg-amber-50 border border-amber-200'
    : isError
    ? 'bg-red-50 border border-red-200'
    : 'bg-white border border-slate-200'

  return (
    <div className="flex justify-start mb-5">
      <div className="max-w-2xl w-full">
        {/* Answer bubble */}
        <div className={`${bubbleClass} rounded-2xl rounded-tl-sm shadow-sm px-5 py-4`}>
          {isRefused && (
            <div className="flex items-center gap-2 mb-2 text-amber-700">
              <span className="text-lg">🤷</span>
              <span className="text-xs font-semibold uppercase tracking-wide">Out of scope</span>
            </div>
          )}
          {isError && (
            <div className="flex items-center gap-2 mb-2 text-red-700">
              <span className="text-lg">⚠️</span>
              <span className="text-xs font-semibold uppercase tracking-wide">Error</span>
            </div>
          )}

          <p className={`text-sm leading-relaxed whitespace-pre-wrap ${
            isRefused ? 'text-amber-800' : isError ? 'text-red-800' : 'text-slate-800'
          } ${isStreaming ? 'streaming-cursor' : ''}`}>
            {message.content || (isStreaming ? '' : '—')}
          </p>

          {/* Citations inline (from parsed <CITATIONS> block) */}
          {!isRefused && !isError && message.citations?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-1.5">
              {message.citations.map((c, i) => (
                <span key={i} className="citation-badge">
                  📄 {c.doc}, p.{c.page}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Sources toggle */}
        {message.sources?.length > 0 && (
          <div className="mt-2">
            <button
              onClick={() => setSourcesOpen(o => !o)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-indigo-600 transition-colors px-1 py-0.5 rounded"
            >
              <span>{sourcesOpen ? '▲' : '▼'}</span>
              <span>{sourcesOpen ? 'Hide' : 'Show'} {message.sources.length} source{message.sources.length > 1 ? 's' : ''}</span>
            </button>

            {sourcesOpen && (
              <div className="mt-2 space-y-2">
                {message.sources.map((src, i) => (
                  <SourceCard key={i} source={src} index={i + 1} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
