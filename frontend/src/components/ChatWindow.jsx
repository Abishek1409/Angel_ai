import React, { useEffect, useRef, useState } from 'react'
import MessageBubble from './MessageBubble'

const SUGGESTIONS = [
  'Summarize the document for me',
  'What are the key findings?',
  'List the main topics covered',
  'Explain the most important concept',
]

export default function ChatWindow({ messages, loading, onSend }) {
  const [query, setQuery] = useState('')
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = () => {
    const q = query.trim()
    if (!q || loading) return
    setQuery('')
    onSend(q)
    // reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e) => {
    setQuery(e.target.value)
    const el = textareaRef.current
    if (el) { el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 160)}px` }
  }

  return (
    <div className="chat-area">
      <div className="chat-bg" aria-hidden="true" />

      <div className="messages-container" role="log" aria-label="Chat messages" aria-live="polite">
        {messages.length === 0 && !loading ? (
          <div className="empty-state">
            <div className="empty-angel" aria-hidden="true">✨</div>
            <h1 className="empty-title">Hi, I'm Angel AI</h1>
            <p className="empty-subtitle">
              Upload a document from the sidebar and ask me anything about it.
              I'll use RAG to find the most relevant information and answer precisely.
            </p>
            <div className="suggestion-chips" role="list">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  className="chip"
                  role="listitem"
                  onClick={() => { setQuery(s); textareaRef.current?.focus() }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {loading && (
              <div className="message-row assistant" aria-label="Angel AI is thinking">
                <div className="avatar ai" aria-hidden="true">✨</div>
                <div className="typing-indicator">
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="input-bar">
        <div className="input-row">
          <textarea
            ref={textareaRef}
            id="chat-input"
            className="chat-input"
            placeholder="Ask anything about your documents…"
            value={query}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            rows={1}
            aria-label="Chat input"
          />
          <button
            id="send-btn"
            className="send-btn"
            onClick={handleSend}
            disabled={!query.trim() || loading}
            aria-label="Send message"
          >
            ➤
          </button>
        </div>
        <p className="input-hint">Press Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  )
}
