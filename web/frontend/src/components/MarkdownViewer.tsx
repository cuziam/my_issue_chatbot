import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'

const components: Components = {
  // Style diff code blocks with line-level coloring
  pre({ children, ...props }) {
    return (
      <pre {...props} className="bg-slate-800 text-slate-200 p-4 rounded-lg overflow-x-auto my-3 border border-slate-700 text-[0.85rem] leading-relaxed">
        {children}
      </pre>
    )
  },
  code({ children, className, ...props }) {
    const isInline = !className
    if (isInline) {
      return (
        <code
          {...props}
          className="bg-gray-100 text-red-600 px-1.5 py-0.5 rounded text-[0.85em] font-medium border border-gray-200"
        >
          {children}
        </code>
      )
    }
    // Block code - handle diff highlighting
    const content = String(children)
    if (className?.includes('language-diff')) {
      return (
        <code {...props} className={className}>
          {content.split('\n').map((line, i) => {
            let lineClass = ''
            if (line.startsWith('+') && !line.startsWith('+++')) lineClass = 'text-green-400'
            else if (line.startsWith('-') && !line.startsWith('---')) lineClass = 'text-red-400'
            else if (line.startsWith('@@')) lineClass = 'text-cyan-400'
            return (
              <span key={i} className={lineClass}>
                {line}
                {'\n'}
              </span>
            )
          })}
        </code>
      )
    }
    return <code {...props} className={className}>{children}</code>
  },
}

export default function MarkdownViewer({ content }: { content: string }) {
  return (
    <div className="markdown-body text-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
