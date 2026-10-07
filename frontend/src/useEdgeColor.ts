import { useEffect, useState } from 'react'

/**
 * Samples a photo's top-left pixel so the frame around it can match.
 * Many catalogue photos have a black background baked in, others white.
 */
export function useEdgeColor(src: string): string | undefined {
  const [color, setColor] = useState<string>()

  useEffect(() => {
    let cancelled = false
    const img = new Image()
    img.src = src
    img
      .decode()
      .then(() => {
        const canvas = document.createElement('canvas')
        canvas.width = canvas.height = 1
        const ctx = canvas.getContext('2d')
        if (!ctx || cancelled) return
        ctx.drawImage(img, 2, 2, 1, 1, 0, 0, 1, 1)
        const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data
        setColor(`rgb(${r}, ${g}, ${b})`)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [src])

  return color
}
