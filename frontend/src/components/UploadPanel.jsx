import React, { useRef } from 'react'

const SUPPORTED_TYPES = '.pdf,.docx,.txt,.md,.csv'

export default function UploadPanel({ docs, onUpload, onClear, uploading }) {
  const fileRef = useRef(null)

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return
    for (const file of Array.from(files)) {
      await onUpload(file)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.currentTarget.classList.remove('drag-over')
    handleFiles(e.dataTransfer.files)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.currentTarget.classList.add('drag-over')
  }

  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('drag-over')
  }

  const getDocIcon = (name) => {
    if (!name) return '📄'
    const ext = name.split('.').pop()?.toLowerCase()
    if (ext === 'pdf') return '📕'
    if (ext === 'docx' || ext === 'doc') return '📘'
    if (ext === 'csv') return '📊'
    if (ext === 'md') return '📝'
    return '📄'
  }

  return (
    <>
      <span className="sidebar-section-title">Documents</span>

      <div
        className="upload-zone"
        onClick={() => !uploading && fileRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && fileRef.current?.click()}
        aria-label="Upload document"
      >
        <div className="upload-icon">☁️</div>
        <div className="upload-hint">
          <strong>Drag & drop</strong> or click to upload
          <small>PDF, DOCX, TXT, MD, CSV</small>
        </div>
        {uploading && <div className="upload-progress"><div className="upload-progress-bar" /></div>}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept={SUPPORTED_TYPES}
        multiple
        style={{ display: 'none' }}
        id="file-upload-input"
        onChange={(e) => { handleFiles(e.target.files); e.target.value = '' }}
      />

      <button
        id="upload-btn"
        className="upload-btn"
        disabled={uploading}
        onClick={() => fileRef.current?.click()}
      >
        {uploading ? '⏳ Processing…' : '＋ Upload Document'}
      </button>

      {docs.length > 0 && (
        <>
          <span className="sidebar-section-title" style={{ marginTop: 4 }}>
            Loaded ({docs.length})
          </span>
          <div className="doc-list">
            {docs.map((doc, i) => (
              <div key={i} className="doc-item">
                <span className="doc-icon">{getDocIcon(doc.filename)}</span>
                <span className="doc-name" title={doc.filename}>{doc.filename}</span>
                <span className="doc-chunks">{doc.chunks}c</span>
              </div>
            ))}
          </div>
          <button id="clear-docs-btn" className="clear-btn" onClick={onClear}>
            🗑 Clear All
          </button>
        </>
      )}
    </>
  )
}
