import { useEffect, useState } from 'react'
import { formatPrice } from '../api'
import { useCart } from '../context/CartContext'
import type { Product } from '../types'
import { useEdgeColor } from '../useEdgeColor'
import { CloseIcon } from './Icons'
import Overlay from './Overlay'
import ZoomImage from './ZoomImage'

interface Props {
  product: Product
  onClose: () => void
}

export default function ProductModal({ product, onClose }: Props) {
  const { add } = useCart()
  // The catalogue has one photo per product today; the gallery is ready for more.
  // Real product photo first; a reviewed AI on-model photo (Problem 10) as the second view.
  const images = product.model_image_url ? [product.image_url, product.model_image_url] : [product.image_url]
  const [activeImage, setActiveImage] = useState(0)
  const frameColor = useEdgeColor(images[activeImage])
  const [size, setSize] = useState<string | null>(null)
  const [added, setAdded] = useState(false)

  useEffect(() => {
    if (!added) return
    const t = setTimeout(() => setAdded(false), 1800)
    return () => clearTimeout(t)
  }, [added])

  const selected = product.sizes.find((s) => s.size === size)

  const putIntoCart = () => {
    if (!size) return
    add(product, size)
    setAdded(true)
  }

  return (
    <Overlay onClose={onClose} label={product.name}>
      <div className="product-modal">
        <button className="modal-close" aria-label="Close" onClick={onClose}>
          <CloseIcon />
        </button>

        <div className="product-modal__gallery" style={{ background: frameColor }}>
          <ZoomImage className="product-modal__image" src={images[activeImage]} alt={product.name} />
          {images[activeImage] === product.model_image_url && (
            <span className="ai-label ai-label--modal">AI-generated preview · see the first photo for the exact product</span>
          )}
          {images.length > 1 && (
            <div className="thumbs">
              {images.map((src, i) => (
                <button
                  key={src}
                  className={`thumb${i === activeImage ? ' thumb--active' : ''}`}
                  onClick={() => setActiveImage(i)}
                  aria-label={`Show image ${i + 1}`}
                >
                  <img src={src} alt="" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="product-modal__details">
          <h2 className="product-modal__title">{product.name}</h2>
          <p className="product-modal__price">{formatPrice(product.price)}</p>
          <p className="product-modal__desc">{product.description}</p>

          <div className="size-picker">
            <span className="eyebrow">Size</span>
            <div className="size-grid" role="radiogroup" aria-label="Size">
              {product.sizes.map((s) => (
                <button
                  key={s.size}
                  role="radio"
                  aria-checked={size === s.size}
                  className={`size-btn${size === s.size ? ' size-btn--selected' : ''}`}
                  disabled={!s.in_stock}
                  title={s.in_stock ? `Size ${s.size}` : `Size ${s.size} is out of stock`}
                  onClick={() => setSize(s.size)}
                >
                  {s.size}
                </button>
              ))}
            </div>
            {product.sizes.some((s) => !s.in_stock) && (
              <p className="size-legend">Greyed-out sizes are out of stock for now.</p>
            )}
          </div>

          <div className="purchase">
            <p className={`selection-note${size ? ' selection-note--set' : ''}`} aria-live="polite">
              {!product.in_stock
                ? 'This item is sold out in every size right now.'
                : size
                  ? <>You selected size <strong>{size}</strong>{selected && selected.quantity <= 3 && ` — only ${selected.quantity} left!`}</>
                  : 'Please select a size.'}
            </p>
            <button className="btn btn--primary btn--block" disabled={!size} onClick={putIntoCart}>
              {added ? 'Added to Cart ✓' : 'Put Into Cart'}
            </button>
          </div>
        </div>
      </div>
    </Overlay>
  )
}
