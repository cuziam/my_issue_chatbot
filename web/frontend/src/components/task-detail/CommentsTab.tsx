import type { Comment } from '../../types'
import { formatDate } from '../../utils/format'
import EmptyState from '../ui/EmptyState'

export default function CommentsTab({ comments }: { comments: Comment[] }) {
  if (comments.length === 0) {
    return <EmptyState text="No comments" />
  }

  return (
    <div className="space-y-0">
      {comments.map((comment, idx) => (
        <div key={idx} className={`py-4 ${idx > 0 ? 'border-t border-slate-100' : ''}`}>
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-slate-400 to-slate-600 flex items-center justify-center flex-shrink-0">
              <span className="text-white text-[10px] font-medium">{comment.user?.charAt(0)?.toUpperCase() || '?'}</span>
            </div>
            <span className="text-sm font-medium text-slate-800">{comment.user}</span>
            <span className="text-xs text-slate-400">{formatDate(comment.date)}</span>
          </div>
          <div className="ml-9.5 text-sm text-slate-600 leading-relaxed whitespace-pre-wrap pl-[38px]">{comment.comment}</div>
        </div>
      ))}
    </div>
  )
}
