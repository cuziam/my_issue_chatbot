import type { TaskDetail as TaskDetailType } from '../../types'
import MarkdownViewer from '../MarkdownViewer'
import EmptyState from '../ui/EmptyState'

function attachmentToUrl(path: string): string {
  const tasksIndex = path.replace(/\\/g, '/').indexOf('tasks/')
  if (tasksIndex === -1) return path
  return '/files/' + path.replace(/\\/g, '/').substring(tasksIndex)
}

function isImageFile(name: string): boolean {
  return /\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i.test(name)
}

export default function DescriptionTab({ task }: { task: TaskDetailType }) {
  const imageAttachments = task.attachments.filter((a) => isImageFile(a.original_name))

  return (
    <div>
      {task.markdown_description ? (
        <MarkdownViewer content={task.markdown_description} />
      ) : task.description ? (
        <pre className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed">{task.description}</pre>
      ) : (
        <EmptyState text="No description available" />
      )}

      {imageAttachments.length > 0 && (
        <div className="mt-8 pt-6 border-t border-slate-200">
          <h4 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
            Attached Images
          </h4>
          <div className="grid gap-4">
            {imageAttachments.map((att, idx) => (
              <div key={idx} className="group">
                <p className="text-xs text-slate-400 mb-1.5">{att.original_name}</p>
                <img
                  src={attachmentToUrl(att.path)}
                  alt={att.original_name}
                  className="max-w-full rounded-lg border border-slate-200 shadow-sm group-hover:shadow-md transition-shadow"
                  loading="lazy"
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
