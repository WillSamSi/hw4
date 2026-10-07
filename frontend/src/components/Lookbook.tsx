import { Link } from 'react-router-dom'

interface Props {
  photos: string[]
  eyebrow: string
  title: string
  cta: string
}

/** Full-width strip of portrait model photos with a headline overlay. */
export default function Lookbook({ photos, eyebrow, title, cta }: Props) {
  return (
    <section className="lookbook">
      <div className="lookbook__strip">
        {photos.map((src) => (
          <img key={src} src={src} alt="" loading="lazy" />
        ))}
      </div>
      <div className="lookbook__content">
        <span className="eyebrow eyebrow--light">{eyebrow}</span>
        <h2>{title}</h2>
        <Link to="/products" className="btn btn--light">
          {cta}
        </Link>
      </div>
    </section>
  )
}
