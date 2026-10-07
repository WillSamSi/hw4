import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

export interface Slide {
  src: string
  /** CSS object-position, to keep faces in frame when cropping. */
  position?: string
}

interface Props {
  slides: Slide[]
  eyebrow: string
  title: string
  cta: string
  /** Milliseconds per slide. */
  interval?: number
}

/** Full-frame model photo slideshow with a headline and call to action. */
export default function ModelBanner({ slides, eyebrow, title, cta, interval = 5000 }: Props) {
  const [active, setActive] = useState(0)

  useEffect(() => {
    if (slides.length < 2) return
    const t = setInterval(() => setActive((i) => (i + 1) % slides.length), interval)
    return () => clearInterval(t)
  }, [slides.length, interval, active])

  return (
    <section className="model-banner">
      {slides.map((s, i) => (
        <img
          key={s.src}
          src={s.src}
          alt=""
          className={i === active ? 'is-active' : ''}
          style={{ objectPosition: s.position }}
          loading={i === 0 ? 'eager' : 'lazy'}
        />
      ))}
      <div className="model-banner__content">
        <span className="eyebrow eyebrow--light">{eyebrow}</span>
        <h2>{title}</h2>
        <Link to="/products" className="btn btn--light">
          {cta}
        </Link>
      </div>
      {slides.length > 1 && (
        <div className="model-banner__dots">
          {slides.map((s, i) => (
            <button
              key={s.src}
              aria-label={`Show photo ${i + 1}`}
              aria-current={i === active}
              className={i === active ? 'is-active' : ''}
              onClick={() => setActive(i)}
            />
          ))}
        </div>
      )}
    </section>
  )
}
