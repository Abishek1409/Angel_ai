import React, { useCallback, useReducer, useRef } from 'react'
import './index.css'
import ChatWindow from './components/ChatWindow'
import UploadPanel from './components/UploadPanel'

// ── State ──────────────────────────────────────────
const initialState = {
  messages: [],
  docs: [],
  uploading: false,
  chatLoading: false,
  toasts: [],
}

let msgCounter = 0
let toastCounter = 0

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.payload] }
    case 'ADD_DOC':
      return { ...state, docs: [...state.docs, action.payload] }
    case 'CLEAR_DOCS':
      return { ...state, docs: [], messages: [] }
    case 'SET_UPLOADING':
      return { ...state, uploading: action.payload }
    case 'SET_LOADING':
      return { ...state, chatLoading: action.payload }
    case 'ADD_TOAST':
      return { ...state, toasts: [...state.toasts, action.payload] }
    case 'REMOVE_TOAST':
      return { ...state, toasts: state.toasts.filter(t => t.id !== action.payload) }
    default:
      return state
  }
}

// ── App ─────────────────────────────────────────────
export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const toastTimeouts = useRef({})

  const showToast = useCallback((msg, type = 'info', duration = 3500) => {
    const id = ++toastCounter
    dispatch({ type: 'ADD_TOAST', payload: { id, msg, type } })
    toastTimeouts.current[id] = setTimeout(() => {
      dispatch({ type: 'REMOVE_TOAST', payload: id })
    }, duration)
  }, [])

  const handleUpload = useCallback(async (file) => {
    dispatch({ type: 'SET_UPLOADING', payload: true })
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('/api/upload', { method: 'POST', body: formData })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload failed')
      dispatch({
        type: 'ADD_DOC',
        payload: { filename: data.filename, chunks: data.chunks_added },
      })
      showToast(`✅ "${data.filename}" — ${data.chunks_added} chunks indexed`, 'success')
    } catch (err) {
      showToast(`❌ ${err.message}`, 'error', 5000)
    } finally {
      dispatch({ type: 'SET_UPLOADING', payload: false })
    }
  }, [showToast])

  const handleClear = useCallback(async () => {
    try {
      await fetch('/api/documents', { method: 'DELETE' })
      dispatch({ type: 'CLEAR_DOCS' })
      showToast('🗑 All documents cleared', 'info')
    } catch {
      showToast('Failed to clear documents', 'error')
    }
  }, [showToast])

  const handleSend = useCallback(async (query) => {
    const userMsg = { id: ++msgCounter, role: 'user', content: query }
    dispatch({ type: 'ADD_MESSAGE', payload: userMsg })
    dispatch({ type: 'SET_LOADING', payload: true })
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: 5 }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Chat error')
      const aiMsg = {
        id: ++msgCounter,
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
      }
      dispatch({ type: 'ADD_MESSAGE', payload: aiMsg })
    } catch (err) {
      dispatch({
        type: 'ADD_MESSAGE',
        payload: {
          id: ++msgCounter,
          role: 'assistant',
          content: `Sorry, something went wrong: ${err.message}`,
          sources: [],
        },
      })
      showToast(`❌ ${err.message}`, 'error', 5000)
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false })
    }
  }, [showToast])

  return (
    <>
      {/* Toast notifications */}
      <div className="toast-container" aria-live="assertive">
        {state.toasts.map(t => (
          <div key={t.id} className={`toast ${t.type}`} role="alert">
            {t.msg}
          </div>
        ))}
      </div>

      <div className="app-layout">
        {/* Header */}
        <header className="header">
          <div className="logo">
            <div className="logo-icon" aria-hidden="true">✨</div>
            <span className="logo-text">Angel AI</span>
          </div>
          <div className="header-badge">
            <div className="status-dot" aria-hidden="true" />
            NVIDIA NIM · RAG
          </div>
        </header>

        {/* Sidebar */}
        <aside className="sidebar" aria-label="Document management">
          <UploadPanel
            docs={state.docs}
            onUpload={handleUpload}
            onClear={handleClear}
            uploading={state.uploading}
          />
        </aside>

        {/* Chat */}
        <main>
          <ChatWindow
            messages={state.messages}
            loading={state.chatLoading}
            onSend={handleSend}
          />
        </main>
      </div>
    </>
  )
}
