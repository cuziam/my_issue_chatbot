import { useEffect, useCallback, useState } from 'react'
import { createPortal } from 'react-dom'

interface ImageLightboxProps {
  src: string
  alt?: string
  onClose: () => void
}

/**
 * Full-screen image lightbox with zoom support.
 * Renders via Portal at document.body level for proper z-index stacking.
 *
 * - Click image to toggle fit/actual-size zoom
 * - Scroll to zoom in/out
 * - ESC or click backdrop to close
 */
export default function ImageLightbox({ src, alt, onClose }: ImageLightboxProps) {
  const [zoomed, setZoomed] = useState(false)

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose],
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    // Prevent body scroll while lightbox is open
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = prev
    }
  }, [handleKeyDown])

  const content = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Image container */}
      <div
        className={`relative ${zoomed ? 'overflow-auto max-w-full max-h-full' : ''}`}
        onClick={(e) => e.stopPropagation()}
        style={zoomed ? { maxWidth: '100vw', maxHeight: '100vh' } : undefined}
      >
        <img
          src={src}
          alt={alt ?? 'Preview'}
          className={`${
            zoomed
              ? 'max-w-none cursor-zoom-out'
              : 'max-w-[90vw] max-h-[85vh] object-contain cursor-zoom-in'
          } rounded-lg shadow-2xl select-none`}
          onClick={() => setZoomed((z) => !z)}
          draggable={false}
        />
      </div>

      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 w-10 h-10 bg-white/90 rounded-full shadow-lg flex items-center justify-center text-slate-600 hover:text-slate-900 hover:bg-white transition-colors"
        title="Close (Esc)"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Zoom hint */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-black/60 rounded-full text-xs text-white/80 pointer-events-none">
        {zoomed ? 'Click to fit' : 'Click to zoom'} · Esc to close
      </div>
    </div>
  )

  return createPortal(content, document.body)
}
