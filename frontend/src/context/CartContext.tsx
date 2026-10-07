import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import * as api from '../api'
import type { CartItem, Product } from '../types'
import { useAuth } from './AuthContext'

interface CartValue {
  items: CartItem[]
  count: number
  subtotal: number
  add: (product: Product, size: string) => void
  setQty: (productId: string, size: string, qty: number) => void
  remove: (productId: string, size: string) => void
}

const CartContext = createContext<CartValue | null>(null)
/** Guest (logged-out) cart. Once logged in, the cart is saved to the account instead. */
const GUEST_KEY = 'cc-cart'

const readGuestCart = (): CartItem[] => {
  try {
    return JSON.parse(localStorage.getItem(GUEST_KEY) ?? '[]') as CartItem[]
  } catch {
    return []
  }
}

const sameLine = (a: CartItem, b: CartItem) => a.product_id === b.product_id && a.size === b.size

/** Adds guest items into the saved cart (quantities summed, capped at stock). */
function mergeCarts(saved: CartItem[], guest: CartItem[]): CartItem[] {
  const merged = saved.map((i) => ({ ...i }))
  for (const g of guest) {
    const existing = merged.find((m) => sameLine(m, g))
    if (existing) existing.qty = Math.min(existing.qty + g.qty, existing.maxQty || existing.qty + g.qty)
    else merged.push({ ...g })
  }
  return merged
}

/** Whose cart the items belong to: null = guest, number = user id. */
type Owner = number | null

export function CartProvider({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth()
  // The cart is tagged with its owner, so one account's items can never be shown
  // (or saved) under another account, even if a request finishes late.
  const [cart, setCart] = useState<{ owner: Owner; items: CartItem[] }>(() => ({ owner: null, items: readGuestCart() }))
  const owner: Owner = user?.id ?? null
  const items = ready && cart.owner === owner ? cart.items : []

  // undefined = auth not checked yet; null = guest; number = logged-in user id
  const lastUserId = useRef<Owner | undefined>(undefined)
  const needsSave = useRef(false)

  // Log in → load the saved cart and fold in anything added as a guest.
  // Log out → clear the cart from this device (it stays saved on the account).
  useEffect(() => {
    if (!ready) return
    const prev = lastUserId.current
    if (prev === owner) return
    lastUserId.current = owner
    needsSave.current = false

    if (owner === null) {
      if (prev !== undefined) {
        localStorage.removeItem(GUEST_KEY)
        setCart({ owner: null, items: [] })
      }
      return
    }

    // Only a cart left by a guest session (not by a previous account) is merged in.
    const guest = prev === null || prev === undefined ? readGuestCart() : []
    localStorage.removeItem(GUEST_KEY)
    api
      .fetchCart()
      .then((saved) => (guest.length ? api.saveCart(mergeCarts(saved, guest)) : saved))
      .then((loaded) => {
        // Ignore the response if someone else has logged in since this request started.
        if (lastUserId.current === owner) setCart({ owner, items: loaded })
      })
      .catch(() => {})
  }, [owner, ready])

  // Persist changes: to localStorage for guests, to the account (debounced) when logged in.
  useEffect(() => {
    if (!ready || cart.owner !== owner) return
    if (owner === null) {
      localStorage.setItem(GUEST_KEY, JSON.stringify(cart.items))
      return
    }
    if (!needsSave.current) return
    // Cleared if the user changes before it fires, so it can't save into another account.
    const t = setTimeout(() => {
      needsSave.current = false
      api.saveCart(cart.items).catch(() => {})
    }, 400)
    return () => clearTimeout(t)
  }, [cart, owner, ready])

  const update = (fn: (prev: CartItem[]) => CartItem[]) => {
    needsSave.current = true
    // Edits always apply to the current owner's cart.
    setCart((c) => ({ owner, items: fn(c.owner === owner ? c.items : []) }))
  }

  const add = (product: Product, size: string) => {
    const stock = product.sizes.find((s) => s.size === size)
    if (!stock?.in_stock) return
    update((prev) => {
      const existing = prev.find((i) => i.product_id === product.product_id && i.size === size)
      if (existing) {
        return prev.map((i) => (i === existing ? { ...i, qty: Math.min(i.qty + 1, stock.quantity), maxQty: stock.quantity } : i))
      }
      return [
        ...prev,
        {
          product_id: product.product_id,
          name: product.name,
          price: product.price,
          image_url: product.image_url,
          size,
          qty: 1,
          maxQty: stock.quantity,
        },
      ]
    })
  }

  const setQty = (productId: string, size: string, qty: number) =>
    update((prev) =>
      prev
        .map((i) =>
          i.product_id === productId && i.size === size ? { ...i, qty: i.maxQty > 0 ? Math.min(qty, i.maxQty) : qty } : i,
        )
        .filter((i) => i.qty > 0),
    )

  const remove = (productId: string, size: string) =>
    update((prev) => prev.filter((i) => !(i.product_id === productId && i.size === size)))

  // Sold-out lines stay visible but don't count toward the total.
  const available = items.filter((i) => i.maxQty > 0)
  const count = available.reduce((n, i) => n + i.qty, 0)
  const subtotal = available.reduce((n, i) => n + i.qty * i.price, 0)

  return (
    <CartContext.Provider value={{ items, count, subtotal, add, setQty, remove }}>
      {children}
    </CartContext.Provider>
  )
}

export function useCart() {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used inside CartProvider')
  return ctx
}
