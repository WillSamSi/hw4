import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { fetchRecommended } from '../api'
import { ChevronLeft, ChevronRight } from '../components/Icons'
import Lookbook from '../components/Lookbook'
import ModelBanner from '../components/ModelBanner'
import ProductCard from '../components/ProductCard'
import VisitUs from '../components/VisitUs'
import { MODEL_PHOTOS } from '../store'
import type { Product } from '../types'

export default function Home() {
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState(false)
  const { hash } = useLocation()

  useEffect(() => {
    fetchRecommended().then(setProducts).catch(() => setError(true))
  }, [])

  // "About Us" in the nav links to /#about; scroll there once the page is rendered.
  useEffect(() => {
    if (hash) document.querySelector(hash)?.scrollIntoView({ behavior: 'smooth' })
  }, [hash])

  return (
    <>
      <section className="section">
        <div className="container">
          <span className="eyebrow">Cold-Weather Picks</span>
          <h1 className="section-title">Weather's Getting Cold, But We Keep You Warm</h1>
          {error ? (
            <p className="muted">We couldn't load products. Is the backend running?</p>
          ) : (
            <Carousel products={products} />
          )}
        </div>
      </section>

      <ModelBanner
        slides={MODEL_PHOTOS.lifestyle}
        eyebrow="New Haven Winter Ready"
        title="Layer Up, Bulldogs"
        cta="Shop Hoodies & Crewnecks"
      />

      <section id="about" className="section about">
        <div className="container about__inner">
          <span className="eyebrow">Who We Are</span>
          <h2 className="section-title">About Us</h2>
          <p>
            We're Yale University's official merch shop. From clothing and accessories to goods for your dorm or
            home, we've got you covered through your years at Yale — plus keepsakes to remember your time in New
            Haven.
          </p>
          <p>
            Want something one-of-a-kind? We also do fully custom merchandise. Pick any of our products as your
            base, treat it as your canvas, and we'll help bring your design to life.
          </p>
        </div>
      </section>

      <Lookbook
        photos={MODEL_PHOTOS.lookbook}
        eyebrow="Make It Yours"
        title="Your Design, Our Gear"
        cta="Shop All Products"
      />

      <VisitUs />
    </>
  )
}

function Carousel({ products }: { products: Product[] }) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [atStart, setAtStart] = useState(true)
  const [atEnd, setAtEnd] = useState(false)

  const update = () => {
    const el = trackRef.current
    if (!el) return
    setAtStart(el.scrollLeft <= 4)
    setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 4)
  }

  useEffect(update, [products])

  const scrollBy = (dir: 1 | -1) => {
    const el = trackRef.current
    if (el) el.scrollBy({ left: dir * el.clientWidth, behavior: 'smooth' })
  }

  return (
    <div className="carousel">
      {!atStart && (
        <button className="carousel__btn carousel__btn--prev" aria-label="Previous products" onClick={() => scrollBy(-1)}>
          <ChevronLeft />
        </button>
      )}
      <div className="carousel__track" ref={trackRef} onScroll={update}>
        {products.length === 0
          ? Array.from({ length: 4 }, (_, i) => <div key={i} className="product-card product-card--skeleton" />)
          : products.map((p) => <ProductCard key={p.product_id} product={p} />)}
      </div>
      {!atEnd && (
        <button className="carousel__btn carousel__btn--next" aria-label="More recommended products" onClick={() => scrollBy(1)}>
          <ChevronRight />
        </button>
      )}
    </div>
  )
}
