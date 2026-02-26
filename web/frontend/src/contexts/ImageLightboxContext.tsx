import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import ImageLightbox from '../components/ImageLightbox'

type OpenLightbox = (src: string, alt?: string) => void

const ImageLightboxContext = createContext<OpenLightbox>(() => {})

/**
 * Global image lightbox provider.
 * Wrap the app with this to allow any component to open a lightbox via
 * `const openLightbox = useImageLightbox()`.
 */
export function ImageLightboxProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ src: string; alt?: string } | null>(null)

  const open: OpenLightbox = useCallback((src, alt) => {
    setState({ src, alt })
  }, [])

  const close = useCallback(() => setState(null), [])

  return (
    <ImageLightboxContext.Provider value={open}>
      {children}
      {state && <ImageLightbox src={state.src} alt={state.alt} onClose={close} />}
    </ImageLightboxContext.Provider>
  )
}

/**
 * Hook to open the global image lightbox.
 * Returns a function: `openLightbox(src, alt?)`.
 */
export function useImageLightbox(): OpenLightbox {
  return useContext(ImageLightboxContext)
}
