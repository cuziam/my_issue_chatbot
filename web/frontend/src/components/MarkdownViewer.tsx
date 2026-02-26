import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import { useImageLightbox } from '../contexts/ImageLightboxContext'

const baseComponents: Partial<Components> = {
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

/**
 * Pre-process markdown to ensure images are on their own lines (block-level).
 * ClickUp often puts `![img](url)` inline with surrounding text, which causes
 * images to render inside <p> tags alongside text — breaking layout.
 *
 * Strategy: split each line into text-segments and image-segments, then
 * reassemble so images always occupy their own blank-line-separated paragraph.
 */
function isolateImages(md: string): string {
  const imgRe = /!\[[^\]]*\]\([^)]+\)/g
  return md
    .split('\n')
    .flatMap((line) => {
      // Skip code-fence lines, empty lines, lines without images
      if (!imgRe.test(line)) return [line]
      imgRe.lastIndex = 0  // reset after .test()

      // Split the line into alternating text / image tokens
      const tokens: string[] = []
      let lastIdx = 0
      let m: RegExpExecArray | null
      while ((m = imgRe.exec(line)) !== null) {
        if (m.index > lastIdx) tokens.push(line.slice(lastIdx, m.index))
        tokens.push(m[0])
        lastIdx = m.index + m[0].length
      }
      if (lastIdx < line.length) tokens.push(line.slice(lastIdx))

      // If only one token (the image itself, no surrounding text), keep as-is
      if (tokens.length === 1) return [line]

      // Reassemble: text stays together, each image gets its own line with blank-line gaps
      const result: string[] = []
      for (const tok of tokens) {
        const trimmed = tok.trim()
        if (!trimmed) continue
        if (/^!\[/.test(trimmed)) {
          // Image → ensure blank line before + after
          if (result.length > 0 && result[result.length - 1] !== '') result.push('')
          result.push(trimmed)
          result.push('')
        } else {
          result.push(trimmed)
        }
      }
      // Trim trailing blank line
      while (result.length > 0 && result[result.length - 1] === '') result.pop()
      return result
    })
    .join('\n')
}

export default function MarkdownViewer({ content }: { content: string }) {
  const openLightbox = useImageLightbox()

  const processed = useMemo(() => isolateImages(content), [content])

  const components = useMemo<Partial<Components>>(
    () => ({
      ...baseComponents,
      img({ src, alt }) {
        if (!src) return null
        if (src.includes('.clickup-attachments.com/')) {
          return (
            <a href={src} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline">
              [{alt || 'attached image'}]
            </a>
          )
        }
        return (
          <img
            src={src}
            alt={alt ?? ''}
            className="md-image block max-h-80 rounded-lg border border-slate-200/80 shadow-sm cursor-pointer hover:shadow-md hover:border-slate-300 transition-all my-3"
            loading="lazy"
            onClick={(e) => {
              e.preventDefault()
              openLightbox(src, alt ?? undefined)
            }}
          />
        )
      },
    }),
    [openLightbox],
  )

  return (
    <div className="markdown-body text-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {processed}
      </ReactMarkdown>
    </div>
  )
}
