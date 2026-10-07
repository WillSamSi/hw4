import type { CartItem, ChatHistoryMessage, ChatReply, ChatSearch, ChatTurn, PageContext, Product, User } from './types'

/** Error from the API, keeping the status and any per-field messages. */
export class ApiError extends Error {
  status: number
  fields: Record<string, string>

  constructor(status: number, detail: unknown) {
    const fields =
      detail && typeof detail === 'object' && 'fields' in detail ? (detail.fields as Record<string, string>) : {}
    super(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.')
    this.status = status
    this.fields = fields
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    credentials: 'same-origin', // send the HttpOnly session cookie
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json', ...init.headers } : init?.headers,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const post = <T>(url: string, body?: unknown) =>
  request<T>(url, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

// ---------- Catalogue ----------

/** Search filters shared by the chat's "View all" link and the Products page URL. */
export type ProductSearch = Partial<Pick<ChatSearch, 'query' | 'max_price' | 'size'>>

export const searchParamsFor = (s: ProductSearch) => {
  const p = new URLSearchParams()
  if (s.query) p.set('q', s.query)
  if (s.max_price != null) p.set('max_price', String(s.max_price))
  if (s.size) p.set('size', s.size)
  return p
}

/** Products page filters → GET /api/products (Problem 9). Category/price/size rules match the agent's search. */
export interface ProductFilters {
  q?: string
  category?: string
  size?: string
  min_price?: number
  max_price?: number
  in_stock?: boolean
  sort?: string
}

/** All products, or a filtered/sorted view (same ranking as the agent's search_products when `q` is set). */
export const fetchProducts = (filters: ProductFilters = {}) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== '' && v !== false) p.set(k, String(v))
  }
  const qs = p.toString()
  return request<Product[]>(`/api/products${qs ? `?${qs}` : ''}`)
}

export const fetchRecommended = (limit = 12) => request<Product[]>(`/api/products/recommended?limit=${limit}`)

export const fetchProduct = (productId: string) => request<Product>(`/api/products/${encodeURIComponent(productId)}`)

/** Sends a message (plus recent turns for context) to the PydanticAI shop agent. */
/** Guests send recent turns as `history`; for logged-in shoppers the server replays saved history instead. */
export const sendChat = (message: string, history: ChatTurn[], page: PageContext) =>
  post<ChatReply>('/api/chat', { message, history, page })

export const fetchChatHistory = () => request<ChatHistoryMessage[]>('/api/chat/history')

export const clearChatHistory = () => request<void>('/api/chat/history', { method: 'DELETE' })

export const formatPrice = (price: number) => `$${price.toFixed(2)}`

// ---------- Auth ----------

interface ApiUser {
  id: number
  first_name: string
  last_name: string
  email: string
}

const toUser = (u: ApiUser): User => ({ id: u.id, firstName: u.first_name, lastName: u.last_name, email: u.email })

export const fetchMe = () => request<ApiUser>('/api/auth/me').then(toUser)

export const login = (email: string, password: string) =>
  post<ApiUser>('/api/auth/login', { email, password }).then(toUser)

export interface RegisterInput {
  firstName: string
  lastName: string
  email: string
  password: string
  confirmPassword: string
}

export const register = (f: RegisterInput) =>
  post<ApiUser>('/api/auth/register', {
    first_name: f.firstName,
    last_name: f.lastName,
    email: f.email,
    password: f.password,
    confirm_password: f.confirmPassword,
  }).then(toUser)

export const logout = () => post<void>('/api/auth/logout')

// ---------- Saved cart ----------

interface ApiCartLine {
  product_id: string
  name: string
  price: number
  image_url: string
  size: string
  qty: number
  max_qty: number
}

const toCartItem = (l: ApiCartLine): CartItem => ({
  product_id: l.product_id,
  name: l.name,
  price: l.price,
  image_url: l.image_url,
  size: l.size,
  qty: l.qty,
  maxQty: l.max_qty,
})

export const fetchCart = () => request<ApiCartLine[]>('/api/cart').then((ls) => ls.map(toCartItem))

export const saveCart = (items: CartItem[]) =>
  request<ApiCartLine[]>('/api/cart', {
    method: 'PUT',
    body: JSON.stringify({ items: items.map(({ product_id, size, qty }) => ({ product_id, size, qty })) }),
  }).then((ls) => ls.map(toCartItem))
