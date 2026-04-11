import React from 'react'

export default function MessageBubble({ message }) {
  const { role, content, sources } = message
  const isAI = role === 'assistant'

  const formatContent = (text) => {
    // Simple markdown-like: bold, code, paragraphs
    return text.split('\n\n').map((para, i) => (
      <p key={i}>{para.split('\n').map((line, j) => (
        <React.Fragment key={j}>{line}{j < para.split('\n').length - 1 && <br />}</React.Fragment>
      ))}</p>
    ))
  }

  return (
    <div className={`message-row ${role}`} id={`msg-${message.id}`}>
      <div className={`avatar ${isAI ? 'ai' : 'user'}`}>
        {isAI ? '✨' : '👤'}
      </div>
      <div className={`bubble ${isAI ? 'ai' : 'user'}`}>
        {formatContent(content)}
        {isAI && sources && sources.length > 0 && (
          <div className="sources-tag">
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginRight: 4 }}>Sources:</span>
            {sources.map((src, i) => (
              <span key={i} className="source-chip">📎 {src}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
