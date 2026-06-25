import { useRef, useEffect } from 'react'

export default function InputBar({ onSubmit, disabled }) {
  const textareaRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  })

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const val = textareaRef.current?.value?.trim()
    if (!val || disabled) return
    onSubmit(val)
    textareaRef.current.value = ''
    textareaRef.current.style.height = 'auto'
  }

  return (
    <div className="border-t border-slate-200 bg-white px-4 py-3">
      <div className="flex items-end gap-2 max-w-3xl mx-auto">
        <textarea
          ref={textareaRef}
          rows={1}
          disabled={disabled}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? 'Generating answer…' : 'Ask a question about your documents…'}
          className="flex-1 resize-none rounded-xl border border-slate-300 bg-slate-50 px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed transition overflow-hidden"
          style={{ minHeight: '44px', maxHeight: '160px' }}
        />
        <button
          onClick={submit}
          disabled={disabled}
          className="flex-shrink-0 w-10 h-10 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors shadow-sm"
          title="Send (Enter)"
        >
          {disabled ? (
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"/>
            </svg>
          )}
        </button>
      </div>
      <p className="text-center text-xs text-slate-400 mt-2">
        Shift+Enter for newline · Enter to send
      </p>
    </div>
  )
}
