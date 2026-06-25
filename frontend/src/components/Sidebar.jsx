import { useRef, useState } from 'react'

const DOC_COLORS = [
  'bg-indigo-500', 'bg-sky-500', 'bg-emerald-500',
  'bg-amber-500',  'bg-pink-500', 'bg-purple-500',
]

function DocIcon({ name, colorClass }) {
  const initials = name.replace(/[_-]/g, ' ').split(' ')
    .map(w => w[0]?.toUpperCase() || '').slice(0, 2).join('')
  return (
    <div className={`w-7 h-7 rounded-md flex items-center justify-center text-white text-xs font-bold flex-shrink-0 ${colorClass}`}>
      {initials || '?'}
    </div>
  )
}

export default function Sidebar({ documents, indexed, onUpload }) {
  const fileInputRef             = useRef(null)
  const [uploadState, setUpload] = useState('idle')   // idle | uploading | done | error
  const [uploadMsg,   setMsg]    = useState('')

  async function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''   // reset so same file can be re-selected

    setUpload('uploading')
    setMsg(`Indexing ${file.name}…`)

    try {
      const form = new FormData()
      form.append('file', file)

      const res = await fetch(
        (import.meta.env.VITE_API_URL || '/api') + '/ingest/upload',
        { method: 'POST', body: form }
      )

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || res.statusText)
      }

      const data = await res.json()
      setUpload('done')
      setMsg(`✓ ${data.doc_name} — ${data.chunks} chunks indexed`)
      onUpload?.()   // refresh document list in parent

      setTimeout(() => { setUpload('idle'); setMsg('') }, 4000)
    } catch (err) {
      setUpload('error')
      setMsg(err.message || 'Upload failed')
      setTimeout(() => { setUpload('idle'); setMsg('') }, 5000)
    }
  }

  return (
    <aside className="w-64 flex-shrink-0 bg-slate-900 text-slate-100 flex flex-col h-full">
      {/* Header */}
      <div className="px-5 pt-6 pb-4 border-b border-slate-700">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-2xl">📚</span>
          <span className="font-bold text-lg tracking-tight">DocAI</span>
        </div>
        <p className="text-slate-400 text-xs">RAG Document Assistant</p>
      </div>

      {/* Status */}
      <div className="px-5 py-3 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${indexed ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
          <span className="text-xs text-slate-400">
            {indexed ? 'Index ready' : 'Not indexed'}
          </span>
        </div>
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3 px-1">
          Documents ({documents.length})
        </p>
        {documents.length === 0 ? (
          <p className="text-slate-500 text-xs px-1">No documents found</p>
        ) : (
          <ul className="space-y-2">
            {documents.map((doc, i) => (
              <li key={doc}
                  className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-slate-800 transition-colors cursor-default">
                <DocIcon name={doc} colorClass={DOC_COLORS[i % DOC_COLORS.length]} />
                <span className="text-sm text-slate-300 truncate" title={doc}>{doc}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Upload section */}
      <div className="px-4 py-4 border-t border-slate-700 space-y-2">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={handleFileChange}
        />

        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadState === 'uploading'}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg
            bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:cursor-not-allowed
            text-white text-sm font-medium transition-colors"
        >
          {uploadState === 'uploading' ? (
            <>
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z"/>
              </svg>
              Indexing…
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M16 10l-4-4-4 4M12 6v10"/>
              </svg>
              Upload PDF
            </>
          )}
        </button>

        {uploadMsg && (
          <p className={`text-xs px-1 ${
            uploadState === 'error' ? 'text-red-400' :
            uploadState === 'done'  ? 'text-emerald-400' : 'text-slate-400'
          }`}>
            {uploadMsg}
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-slate-700">
        <p className="text-xs text-slate-600">
          Ask anything — answers are cited from your documents only.
        </p>
      </div>
    </aside>
  )
}
