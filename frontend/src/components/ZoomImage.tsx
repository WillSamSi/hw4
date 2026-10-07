import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'

const ZOOM = 1.75 // 175%

interface Props {
  src: string
  alt: string
  className?: string
}

/** Click-to-zoom product photo for the pop-up: "+" cursor to zoom in to 175%, "−" cursor to zoom out.
 *  While zoomed, the magnified area follows the pointer (the spot under the cursor stays under it). */
export default function ZoomImage({ src, alt, className }: Props) {
  const frameRef = useRef<HTMLDivElement>(null)
  const [zoomed, setZoomed] = useState(false)
  const [origin, setOrigin] = useState('50% 50%')
  const [shownSrc, setShownSrc] = useState(src)

  // Switching to another photo always starts un-zoomed.
  if (src !== shownSrc) {
    setShownSrc(src)
    setZoomed(false)
    setOrigin('50% 50%')
  }

  const pointAt = (e: PointerEvent<HTMLDivElement>) => {
    const r = frameRef.current!.getBoundingClientRect()
    const clamp = (v: number) => Math.min(100, Math.max(0, v))
    return `${clamp(((e.clientX - r.left) / r.width) * 100)}% ${clamp(((e.clientY - r.top) / r.height) * 100)}%`
  }

  // A press that barely moves is a click/tap (toggle); a longer drag is panning (touch screens).
  const downAt = useRef<{ x: number; y: number } | null>(null)
  const toggle = (e: PointerEvent<HTMLDivElement>) => {
    const d = downAt.current
    downAt.current = null
    if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) > 6) return
    setOrigin(pointAt(e)) // zoom in on the spot that was clicked
    setZoomed((z) => !z)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setOrigin('50% 50%')
      setZoomed((z) => !z)
    } else if (e.key === 'Escape' && zoomed) {
      e.stopPropagation() // first Esc zooms out; the next one closes the pop-up
      setZoomed(false)
    }
  }

  return (
    <div
      ref={frameRef}
      className={`zoom-frame${zoomed ? ' is-zoomed' : ''}`}
      role="button"
      tabIndex={0}
      aria-label={zoomed ? 'Zoom out of the photo' : 'Zoom in on the photo'}
      aria-pressed={zoomed}
      onPointerDown={(e) => (downAt.current = { x: e.clientX, y: e.clientY })}
      onPointerUp={toggle}
      onPointerMove={(e) => zoomed && setOrigin(pointAt(e))}
      onKeyDown={onKeyDown}
    >
      <img
        className={className}
        src={src}
        alt={alt}
        draggable={false}
        style={{ transformOrigin: origin, transform: zoomed ? `scale(${ZOOM})` : 'none' }}
      />
    </div>
  )
}
