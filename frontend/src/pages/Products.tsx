import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts, formatPrice, type ProductFilters } from '../api'
import ProductCard from '../components/ProductCard'
import type { Product } from '../types'

// Keys match backend tools.CATEGORIES, so the page and the chat agent agree on categories.
const CATEGORIES = [
  { key: '', label: 'All' },
  { key: 'hoodie', label: 'Hoodies' },
  { key: 'crewneck', label: 'Crewnecks' },
  { key: 't-shirt', label: 'T-Shirts' },
  { key: 'quarter-zip', label: 'Quarter-Zips' },
  { key: 'jacket', label: 'Jackets & Fleece' },
  { key: 'long sleeve', label: 'Long Sleeve' },
]
const SIZES = ['S', 'M', 'L', 'XL']
const PRICES: Record<string, { label: string; min?: number; max?: number }> = {
  'under-40': { label: 'Under $40', max: 40 },
  '40-70': { label: '$40–$70', min: 40, max: 70 },
  'over-70': { label: 'Over $70', min: 70 },
}
const SORTS = [
  { key: 'featured', label: 'Featured' },
  { key: 'price_asc', label: 'Price: low to high' },
  { key: 'price_desc', label: 'Price: high to low' },
  { key: 'name', label: 'Name: A to Z' },
]

/** /products with optional URL filters: q, category, size, price, max_price (from the chat), in_stock, sort.
 *  Filters live in the URL, so views can be shared, the back button works, and the chat's
 *  "View all matches" link lands on a filtered view. */
export default function Products() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const size = params.get('size') ?? ''
  const price = params.get('price') ?? ''
  const rawMax = params.get('max_price')
  const inStock = params.get('in_stock') === '1'
  const sort = params.get('sort') ?? 'featured'
  const key = params.toString()

  const [result, setResult] = useState<{ key: string; products: Product[] } | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const band = PRICES[price]
    const filters: ProductFilters = {
      q: q || undefined,
      category: category || undefined,
      size: size || undefined,
      min_price: band?.min,
      max_price: band ? band.max : rawMax ? Number(rawMax) : undefined,
      in_stock: inStock,
      sort,
    }
    let cancelled = false
    fetchProducts(filters)
      .then((products) => !cancelled && setResult({ key, products }))
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
    // `key` captures every URL filter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  /** Update one filter in the URL (pushes history so Back undoes it). */
  // Search box: typing updates results instantly (debounced, replaces history so Back isn't per-keystroke).
  const [searchText, setSearchText] = useState(q)
  const lastQ = useRef(q)
  if (q !== lastQ.current) {
    // URL changed elsewhere (chat "View all", Clear search): keep the box in sync.
    lastQ.current = q
    setSearchText(q)
  }
  useEffect(() => {
    const t = setTimeout(() => {
      if (searchText.trim() === q) return
      const next = new URLSearchParams(params)
      if (searchText.trim()) next.set('q', searchText.trim())
      else next.delete('q')
      lastQ.current = searchText.trim()
      setParams(next, { replace: true })
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText])

  const setFilter = (name: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    if (name === 'price') next.delete('max_price') // a chosen band replaces the chat's raw budget
    setParams(next)
  }
  const clearFilters = () => setParams(q ? new URLSearchParams({ q }) : new URLSearchParams())
  const clearAll = () => setParams(new URLSearchParams())

  const products = result?.key === key ? result.products : null
  const filterCount = [category, size, price || rawMax, inStock ? '1' : '', sort !== 'featured' ? sort : ''].filter(Boolean).length

  return (
    <section className="section">
      <div className="container">
        {q ? (
          <>
            <span className="eyebrow">Search Results</span>
            <h1 className="section-title">“{q}”</h1>
          </>
        ) : (
          <>
            <span className="eyebrow">Shop Bulldog Gear</span>
            <h1 className="section-title">All Products</h1>
          </>
        )}

        <div className="filters" role="region" aria-label="Filter and sort products">
          <label className="search-box">
            <span className="visually-hidden">Search products</span>
            <input
              type="search"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Search hoodies, colleges, colors…"
              aria-label="Search products"
            />
          </label>
          <div className="filters__row" role="group" aria-label="Category">
            {CATEGORIES.map((c) => (
              <button
                key={c.key || 'all'}
                className={`pill${category === c.key ? ' pill--active' : ''}`}
                aria-pressed={category === c.key}
                onClick={() => setFilter('category', c.key)}
              >
                {c.label}
              </button>
            ))}
          </div>

          <div className="filters__row filters__row--controls">
            <div className="filters__group" role="group" aria-label="Size in stock">
              <span className="filters__label">Size</span>
              {SIZES.map((s) => (
                <button
                  key={s}
                  className={`pill pill--size${size === s ? ' pill--active' : ''}`}
                  aria-pressed={size === s}
                  title={`Only items with ${s} in stock`}
                  onClick={() => setFilter('size', size === s ? '' : s)}
                >
                  {s}
                </button>
              ))}
            </div>

            <div className="filters__group" role="group" aria-label="Price">
              <span className="filters__label">Price</span>
              {Object.entries(PRICES).map(([k, band]) => (
                <button
                  key={k}
                  className={`pill${price === k ? ' pill--active' : ''}`}
                  aria-pressed={price === k}
                  onClick={() => setFilter('price', price === k ? '' : k)}
                >
                  {band.label}
                </button>
              ))}
            </div>

            <label className="toggle">
              <input type="checkbox" checked={inStock} onChange={(e) => setFilter('in_stock', e.target.checked ? '1' : '')} />
              <span>In stock only</span>
            </label>

            <label className="sort">
              <span className="filters__label">Sort</span>
              <select value={sort} onChange={(e) => setFilter('sort', e.target.value === 'featured' ? '' : e.target.value)}>
                {SORTS.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="filters__summary" aria-live="polite">
            <span>
              {products ? `${products.length} product${products.length === 1 ? '' : 's'}` : 'Loading…'}
              {rawMax && !price && ` · under ${formatPrice(Number(rawMax))}`}
            </span>
            {(filterCount > 0 || q) && (
              <span className="filters__clear">
                {filterCount > 0 && (
                  <button className="link-btn link-btn--underline" onClick={clearFilters}>
                    Clear filters
                  </button>
                )}
                {q && (
                  <button className="link-btn link-btn--underline" onClick={clearAll}>
                    Clear search · show all products
                  </button>
                )}
              </span>
            )}
          </div>
        </div>

        {error && <p className="muted">We couldn't load products. Is the backend running?</p>}
        {products && products.length === 0 && (
          <p className="muted empty-state">
            Nothing matches those filters right now. Try another size or price, or{' '}
            <button className="link-btn link-btn--underline" onClick={clearFilters}>
              clear the filters
            </button>
            .
          </p>
        )}

        <div className="product-grid">
          {products
            ? products.map((p) => <ProductCard key={p.product_id} product={p} focusSize={size || undefined} />)
            : !error && Array.from({ length: 8 }, (_, i) => <div key={i} className="product-card product-card--skeleton" />)}
        </div>
      </div>
    </section>
  )
}
