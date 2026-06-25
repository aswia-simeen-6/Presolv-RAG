import { useState } from 'react'

function SimBadge({ score }) {
  const pct = Math.round(score * 100)
  const color = pct >= 70 ? 'bg-emerald-100 text-emerald-700'
              : pct >= 50 ? 'bg-sky-100 text-sky-700'
              : 'bg-amber-100 text-amber-700'
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>
      {pct}% match
    </span>
  )
}

export default function SourceCard({ source, index }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden bg-white text-sm">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-slate-50 transition-colors text-left"
      >
        {/* Index badge */}
        <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
          {index}
        </span>

        <div className="flex-1 min-w-0">
          <span className="font-semibold text-slate-800 truncate block">{source.doc_name}</span>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-slate-400 text-xs">Page {source.page_num}</span>
            {source.section_title && source.section_title !== 'General' && (
              <span className="text-xs text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded truncate max-w-[180px]">
                {source.section_title}
              </span>
            )}
            {source.chunk_type === 'image_description' && (
              <span className="text-xs text-violet-600 bg-violet-50 px-1.5 py-0.5 rounded">
                📊 chart
              </span>
            )}
          </div>
        </div>

        <SimBadge score={source.similarity} />

        <span className="text-slate-400 text-xs ml-1">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-slate-100 bg-slate-50">
          <p className="text-slate-600 text-xs leading-relaxed line-clamp-6">
            {source.text}
          </p>
        </div>
      )}
    </div>
  )
}
