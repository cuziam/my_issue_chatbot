import type { TaskDetail as TaskDetailType, Attachment } from '../../types'
import MarkdownViewer from '../MarkdownViewer'
import EmptyState from '../ui/EmptyState'
import { useImageLightbox } from '../../contexts/ImageLightboxContext'

function attachmentToUrl(path: string): string {
  const tasksIndex = path.replace(/\\/g, '/').indexOf('tasks/')
  if (tasksIndex === -1) return path
  return '/files/' + path.replace(/\\/g, '/').substring(tasksIndex)
}

function isImageFile(name: string): boolean {
  return /\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i.test(name)
}

function transformClickUpImages(markdown: string, attachments: Attachment[]): string {
  return markdown.replace(
    /!\[([^\]]*)\]\((https:\/\/t\d+\.p\.clickup-attachments\.com\/[^)]+)\)/g,
    (_match, alt: string, url: string) => {
      // Try matching by original_name in the URL or by alt text pattern (image_N)
      const att = attachments.find((a) => {
        if (a.url && a.url === url) return true
        // Match by original_name appearing in the URL
        if (url.includes(encodeURIComponent(a.original_name)) || url.includes(a.original_name)) return true
        // Match by alt text: "image_N" → "image_N.ext" in original_name
        if (alt && a.original_name.startsWith(alt)) return true
        return false
      })
      if (att) {
        const localUrl = attachmentToUrl(att.path)
        return `![${alt || att.original_name}](${localUrl})`
      }
      // No match: convert to text link
      const label = alt || 'image'
      return `[${label}](${url})`
    }
  )
}

export default function DescriptionTab({ task }: { task: TaskDetailType }) {
  const imageAttachments = task.attachments.filter((a) => isImageFile(a.original_name))
  const openLightbox = useImageLightbox()

  const processedMarkdown = task.markdown_description
    ? transformClickUpImages(task.markdown_description, task.attachments)
    : null

  return (
    <div>
      {processedMarkdown ? (
        <MarkdownViewer content={processedMarkdown} />
      ) : task.description ? (
        <pre className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed">{task.description}</pre>
      ) : (
        <EmptyState text="No description available" />
      )}

      {imageAttachments.length > 0 && (
        <div className="mt-8 pt-6 border-t border-slate-200">
          <h4 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
            Attached Images ({imageAttachments.length})
          </h4>
          <div className="flex flex-wrap gap-3">
            {imageAttachments.map((att, idx) => {
              const url = attachmentToUrl(att.path)
              return (
                <div
                  key={idx}
                  className="group relative cursor-pointer"
                  onClick={() => openLightbox(url, att.original_name)}
                >
                  <img
                    src={url}
                    alt={att.original_name}
                    className="h-36 max-w-64 rounded-lg border border-slate-200 shadow-sm object-cover group-hover:shadow-md group-hover:border-slate-300 transition-all"
                    loading="lazy"
                  />
                  <div className="absolute inset-0 rounded-lg bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                    <svg className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow-lg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                    </svg>
                  </div>
                  <p className="mt-1 text-[11px] text-slate-400 truncate max-w-64">{att.original_name}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
