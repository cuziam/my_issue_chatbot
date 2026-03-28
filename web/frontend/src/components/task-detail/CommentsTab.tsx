import type { Comment } from '../../types'
import { formatDate } from '../../utils/format'
import EmptyState from '../ui/EmptyState'

function CommentItem({ comment, isReply = false }: { comment: Comment; isReply?: boolean }) {
  const avatarSize = isReply ? 'w-6 h-6' : 'w-7 h-7'
  const avatarText = isReply ? 'text-[9px]' : 'text-[10px]'
  const avatarColors = isReply
    ? 'from-violet-400 to-violet-600'
    : 'from-slate-400 to-slate-600'

  return (
    <div className={isReply ? 'py-2.5' : 'py-4'}>
      <div className="flex items-center gap-2.5 mb-1.5">
        <div className={`${avatarSize} rounded-full bg-gradient-to-br ${avatarColors} flex items-center justify-center flex-shrink-0`}>
          <span className={`text-white ${avatarText} font-medium`}>{comment.user?.charAt(0)?.toUpperCase() || '?'}</span>
        </div>
        <span className={`${isReply ? 'text-xs' : 'text-sm'} font-medium text-slate-800`}>{comment.user}</span>
        <span className="text-xs text-slate-400">{formatDate(comment.date)}</span>
      </div>
      <div className={`text-sm text-slate-600 leading-relaxed whitespace-pre-wrap ${isReply ? 'pl-8' : 'pl-[38px]'}`}>
        {comment.comment}
      </div>
    </div>
  )
}

export default function CommentsTab({ comments }: { comments: Comment[] }) {
  if (comments.length === 0) {
    return <EmptyState text="No comments" />
  }

  return (
    <div className="space-y-0">
      {comments.map((comment, idx) => (
        <div key={idx} className={idx > 0 ? 'border-t border-slate-100' : ''}>
          <CommentItem comment={comment} />
          {comment.replies && comment.replies.length > 0 && (
            <div className="ml-10 border-l-2 border-violet-100 pl-4 mb-3">
              {comment.replies.map((reply, rIdx) => (
                <CommentItem key={rIdx} comment={reply} isReply />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
