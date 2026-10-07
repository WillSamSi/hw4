import { useState } from 'react'
import { MAPS_EMBED_URL, MAPS_URL, STORE } from '../store'

/** Bottom of the home page: store photo with address, and a map that opens Google Maps. */
export default function VisitUs() {
  const [today] = useState(() => new Date().getDay())
  return (
    <section className="section visit">
      <div className="container">
        <span className="eyebrow">Find Us in New Haven</span>
        <h2 className="section-title">Come Visit Us!</h2>

        <div className="visit__grid">
          <figure className="visit__store">
            <img src="/models/store-front.jpg" alt={`${STORE.name} storefront on Broadway`} loading="lazy" />
            <figcaption>
              <span className="eyebrow eyebrow--light">Our Store</span>
              <strong>{STORE.street}</strong>
              <span>{STORE.city}</span>
              <dl className="hours">
                {STORE.hours.map((h) => (
                  <div key={h.label} className={h.days.includes(today) ? 'is-today' : ''}>
                    <dt>{h.label}</dt>
                    <dd>{h.time}</dd>
                  </div>
                ))}
              </dl>
            </figcaption>
          </figure>

          <a className="visit__map" href={MAPS_URL} target="_blank" rel="noopener noreferrer" aria-label={`Open ${STORE.address} in Google Maps`}>
            {/* Shown underneath until (or if) the live map loads. */}
            <span className="visit__map-fallback" aria-hidden="true">
              <span className="visit__pin">📍</span>
              <strong>{STORE.street}</strong>
              <span>{STORE.city}</span>
            </span>
            {/* The iframe ignores clicks so the whole tile acts as one link to Google Maps. */}
            <iframe title={`Map of ${STORE.address}`} src={MAPS_EMBED_URL} loading="lazy" tabIndex={-1} />
            <span className="visit__map-cta">Open in Google Maps ↗</span>
          </a>
        </div>
      </div>
    </section>
  )
}
