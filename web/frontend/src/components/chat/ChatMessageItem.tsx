import { useState } from 'react'
import type { ChatMessage, ChatAttachment, CreatedFile } from '../../types'
import MarkdownViewer from '../MarkdownViewer'
import LoadingSpinner from '../LoadingSpinner'
import { formatFileSize, getFileTypeIcon } from './ChatFileList'
import { api } from '../../api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatProgressEvent {
  event: string
  tool?: string
  detail?: string
}

export interface PendingFile {
  file: File
  attachment: ChatAttachment
  previewUrl?: string // object URL for image preview
}

// ---------------------------------------------------------------------------
// Streaming message display (used by ChatPanel during active streaming)
// ---------------------------------------------------------------------------

export interface StreamingMessageProps {
  streamingContent: string
  activeProgressEvents: ChatProgressEvent[]
  activeCreatedFiles: CreatedFile[]
  isLoading: boolean
}

export function StreamingMessage({ streamingContent, activeProgressEvents, activeCreatedFiles, isLoading }: StreamingMessageProps) {
  if (streamingContent) {
    return (
      <div className="flex gap-3">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0 mt-0.5">
          <span className="text-white text-xs font-bold">AI</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="bg-slate-50 rounded-xl px-4 py-3 border border-slate-200 text-sm leading-relaxed whitespace-pre-wrap break-words">
            {streamingContent}
          </div>
          {activeCreatedFiles.length > 0 && (
            <CreatedFilesBar files={activeCreatedFiles} />
          )}
          {activeProgressEvents.length > 0 && (
            <ProgressEvents events={activeProgressEvents} />
          )}
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex gap-3">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0 mt-0.5">
          <span className="text-white text-xs font-bold">AI</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <LoadingSpinner size="sm" />
            {activeProgressEvents.length > 0 ? 'Working...' : 'Thinking...'}
          </div>
          {activeProgressEvents.length > 0 && (
            <ProgressEvents events={activeProgressEvents} />
          )}
          {activeCreatedFiles.length > 0 && (
            <CreatedFilesBar files={activeCreatedFiles} />
          )}
        </div>
      </div>
    )
  }

  return null
}

// ---------------------------------------------------------------------------
// ChatMessageItem — individual message bubble
// ---------------------------------------------------------------------------

export interface ChatMessageItemProps {
  message: ChatMessage
}

export default function ChatMessageItem({ message }: ChatMessageItemProps) {
  const isUser = message.role === 'user'
  const [progressOpen, setProgressOpen] = useState(false)

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
        isUser
          ? 'bg-gradient-to-br from-blue-400 to-blue-600'
          : 'bg-gradient-to-br from-violet-500 to-purple-600'
      }`}>
        <span className="text-white text-xs font-bold">{isUser ? 'U' : 'AI'}</span>
      </div>
      <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : ''}`}>
        <div className={`inline-block max-w-[85%] text-left rounded-xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-slate-50 border border-slate-200'
        }`}>
          {isUser ? (
            <>
              {message.content && <p className="whitespace-pre-wrap">{message.content}</p>}
              {message.attachments && message.attachments.length > 0 && (
                <div className={`flex flex-wrap gap-1 ${message.content ? 'mt-2' : ''}`}>
                  {message.attachments.map((att, i) => (
                    <AttachmentChip key={i} attachment={att} />
                  ))}
                </div>
              )}
            </>
          ) : (
            <MarkdownViewer content={message.content} />
          )}
        </div>
        {!isUser && message.created_files && message.created_files.length > 0 && (
          <CreatedFilesBar files={message.created_files} />
        )}
        {!isUser && message.progress_events && message.progress_events.length > 0 && (
          <div className="mt-1.5">
            <button
              onClick={() => setProgressOpen(!progressOpen)}
              className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
            >
              {progressOpen ? 'Hide' : 'Show'} {message.progress_events.length} tool calls
            </button>
            {progressOpen && <ProgressEvents events={message.progress_events} />}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function AttachmentChip({ attachment }: { attachment: ChatAttachment }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-white/20 rounded text-[11px]">
      <span className="opacity-70">{getFileTypeIcon(attachment.type)}</span>
      <span className="truncate max-w-[100px]">{attachment.name}</span>
    </span>
  )
}

function CreatedFilesBar({ files }: { files: CreatedFile[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {files.map((file, i) => (
        <CreatedFileChip key={i} file={file} />
      ))}
    </div>
  )
}

function CreatedFileChip({ file }: { file: CreatedFile }) {
  const handleDownload = () => {
    if (!file.downloadable) return
    api.chatDownload(file.path)
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border ${
        file.downloadable
          ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
          : 'bg-slate-50 border-slate-200 text-slate-400'
      }`}
    >
      {file.downloadable ? (
        <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ) : (
        <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      )}
      <span className="truncate max-w-[160px]">{file.name}</span>
      {file.size != null && (
        <span className="text-[10px] opacity-60">({formatFileSize(file.size)})</span>
      )}
      {file.downloadable ? (
        <button
          onClick={handleDownload}
          className="ml-0.5 p-0.5 rounded hover:bg-emerald-100 transition-colors"
          title="Download"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
      ) : (
        <span className="text-[10px]">(restricted)</span>
      )}
    </span>
  )
}

export function ProgressEvents({ events }: { events: ChatProgressEvent[] }) {
  return (
    <div className="mt-2 space-y-0.5">
      {events.map((ev, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-slate-400">
          <span className="text-slate-300">{'>'}</span>
          {ev.tool && <span className="font-medium text-slate-500">{ev.tool}:</span>}
          <span className="truncate">{ev.detail}</span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// FilePreview — pending file chip in the input area
// ---------------------------------------------------------------------------

export interface FilePreviewProps {
  pendingFile: PendingFile
  onRemove: () => void
}

export function FilePreview({ pendingFile, onRemove }: FilePreviewProps) {
  const { attachment, previewUrl } = pendingFile

  return (
    <div className="relative group flex items-center gap-2 px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs">
      {previewUrl ? (
        <img src={previewUrl} alt={attachment.name} className="w-8 h-8 rounded object-cover" />
      ) : (
        <span className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center text-[10px] font-bold text-slate-400 uppercase">
          {getFileTypeIcon(attachment.type)}
        </span>
      )}
      <div className="max-w-[120px]">
        <div className="truncate text-slate-700 font-medium">{attachment.name}</div>
        <div className="text-slate-400">{formatFileSize(attachment.size)}</div>
      </div>
      <button
        onClick={onRemove}
        className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-[10px] leading-none"
      >
        x
      </button>
    </div>
  )
}
