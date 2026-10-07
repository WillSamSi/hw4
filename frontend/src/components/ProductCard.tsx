import { formatPrice } from '../api'
import { useOpenProduct } from '../context/ProductModalContext'
import type { Product } from '../types'

const LOW_STOCK_TOTAL = 5 // "Low stock" when fewer than 5 units are left across all sizes
const LOW_SIZE = 3 // per-size "Only N left in XL" (matches LOW_STOCK_THRESHOLD in backend/models.py)

/** One small badge from real inventory (`total_in_stock` and per-size quantities from the API).
 *  With a size filter on (`focusSize`), the badge talks only about that size. */
function stockBadge(p: Product, focusSize?: string): { label: string; tone: 'soldout' | 'low' } | null {
  if (p.total_in_stock === 0) return { label: 'Sold out', tone: 'soldout' }
  if (p.total_in_stock < LOW_STOCK_TOTAL) return { label: 'Low stock', tone: 'low' }
  const low = p.sizes.filter((s) => s.in_stock && s.quantity <= LOW_SIZE && (!focusSize || s.size === focusSize))
  if (low.length === 1) return { label: `Only ${low[0].quantity} left in ${low[0].size}`, tone: 'low' }
  if (low.length > 1)
    return { label: low.length <= 2 ? `Low stock in ${low.map((s) => s.size).join(', ')}` : `Low stock in ${low.length} sizes`, tone: 'low' }
  return null
}

export default function ProductCard({ product, focusSize }: { product: Product; focusSize?: string }) {
  const openProduct = useOpenProduct()
  const badge = stockBadge(product, focusSize)
  return (
    <button className="product-card" onClick={() => openProduct(product)}>
      <div className={`product-card__image${product.model_image_url ? ' product-card__image--model' : ''}`}>
        {product.model_image_url ? (
          <>
            {/* On-model photo by default; hovering swaps to the real product photo. */}
            <img className="img-model" src={product.model_image_url} alt={`${product.name}, worn by a model`} loading="lazy" />
            <img className="img-flat" src={product.image_url} alt={product.name} loading="lazy" />
            <span className="ai-label">AI-generated preview</span>
          </>
        ) : (
          <img src={product.image_url} alt={product.name} loading="lazy" />
        )}
        {badge && <span className={`tag tag--${badge.tone}`}>{badge.label}</span>}
      </div>
      <div className="product-card__body">
        <h3 className="product-card__name">{product.name}</h3>
        <span className="product-card__price">{formatPrice(product.price)}</span>
        <p className="product-card__desc">{product.description}</p>
      </div>
    </button>
  )
}
