import { useRef, useEffect, useCallback } from 'react'
import LoadingSpinner from '../LoadingSpinner'
import { FilePreview } from './ChatMessageItem'
import type { PendingFile } from './ChatMessageItem'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatInputProps {
  inputText: string
  onInputChange: (text: string) => void
  onSend: () => void
  onCancel: () => void
  onFiles: (files: FileList | File[]) => void
  onRemoveFile: (index: number) => void
  pendingFiles: PendingFile[]
  uploadingCount: number
  isLoading: boolean
  isDragOver: boolean
  onDragOver: (e: React.DragEvent) => void
  onDragLeave: (e: React.DragEvent) => void
  onDrop: (e: React.DragEvent) => void
  placeholder: string
  canSend: boolean
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
  fileInputRef: React.RefObject<HTMLInputElement | null>
}

// ---------------------------------------------------------------------------
// ChatInput — message input area + file attach + drag-and-drop + send button
// ---------------------------------------------------------------------------

export default function ChatInput({
  inputText,
  onInputChange,
  onSend,
  onCancel,
  onFiles,
  onRemoveFile,
  pendingFiles,
  uploadingCount,
  isLoading,
  isDragOver,
  onDragOver,
  onDragLeave,
  onDrop,
  placeholder,
  canSend,
  textareaRef,
  fileInputRef,
}: ChatInputProps) {

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px'
    }
  }, [inputText, textareaRef])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }, [onSend])

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData.items
    const imageFiles: File[] = []
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const file = items[i].getAsFile()
        if (file) {
          // Generate a name for pasted images
          const ext = file.type.split('/')[1] || 'png'
          const named = new File([file], `pasted_image.${ext}`, { type: file.type })
          imageFiles.push(named)
        }
      }
    }
    if (imageFiles.length > 0) {
      e.preventDefault()
      onFiles(imageFiles)
    }
  }, [onFiles])

  return (
    <>
      {/* File preview area */}
      {(pendingFiles.length > 0 || uploadingCount > 0) && (
        <div className="px-5 py-2 border-t border-slate-100 bg-slate-50/80">
          <div className="flex flex-wrap gap-2">
            {pendingFiles.map((pf, idx) => (
              <FilePreview key={idx} pendingFile={pf} onRemove={() => onRemoveFile(idx)} />
            ))}
            {uploadingCount > 0 && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-500">
                <LoadingSpinner size="sm" />
                Uploading...
              </div>
            )}
          </div>
        </div>
      )}

      {/* Input area */}
      <div
        className={`px-5 py-4 border-t border-slate-200 bg-slate-50/50 transition-colors ${isDragOver ? 'bg-violet-50 border-violet-300' : ''}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {isDragOver && (
          <div className="text-center text-sm text-violet-600 font-medium py-2 mb-2">
            Drop files here to attach
          </div>
        )}
        <div className="flex gap-2 items-end">
          {/* Attach button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            className="p-2.5 text-slate-400 hover:text-violet-600 hover:bg-violet-50 rounded-xl transition-colors disabled:opacity-50 flex-shrink-0"
            title="Attach file"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                onFiles(e.target.files)
                e.target.value = '' // reset so same file can be re-selected
              }
            }}
          />
          <textarea
            ref={textareaRef}
            value={inputText}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={placeholder}
            disabled={isLoading}
            rows={1}
            className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent disabled:opacity-50 resize-none leading-relaxed"
            style={{ minHeight: '42px', maxHeight: '160px' }}
          />
          {isLoading ? (
            <button
              onClick={onCancel}
              className="px-4 py-2.5 bg-red-600 text-white rounded-xl hover:bg-red-700 text-sm font-medium transition-colors flex-shrink-0"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={onSend}
              disabled={!canSend}
              className="px-4 py-2.5 bg-violet-600 text-white rounded-xl hover:bg-violet-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </>
  )
}
