import { createContext, useContext, useState, type ReactNode } from 'react'
import ProductModal from '../components/ProductModal'
import type { Product } from '../types'

const ProductModalContext = createContext<((product: Product) => void) | null>(null)

/** Which product the shopper is looking at; sent to the chat agent as page context. */
interface Viewing {
  current: Product | null
  lastViewed: Product | null
}
const ViewingContext = createContext<Viewing>({ current: null, lastViewed: null })

/** Lets any product card open the single-item pop-up over the current page. */
export function ProductModalProvider({ children }: { children: ReactNode }) {
  const [product, setProduct] = useState<Product | null>(null)
  const [lastViewed, setLastViewed] = useState<Product | null>(null)

  const open = (p: Product) => {
    setProduct(p)
    setLastViewed(p)
  }

  return (
    <ProductModalContext.Provider value={open}>
      <ViewingContext.Provider value={{ current: product, lastViewed }}>
        {children}
        {product && <ProductModal product={product} onClose={() => setProduct(null)} />}
      </ViewingContext.Provider>
    </ProductModalContext.Provider>
  )
}

export function useOpenProduct() {
  const ctx = useContext(ProductModalContext)
  if (!ctx) throw new Error('useOpenProduct must be used inside ProductModalProvider')
  return ctx
}

export const useViewing = () => useContext(ViewingContext)
