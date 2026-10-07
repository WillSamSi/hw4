export interface SizeStock {
  size: string
  quantity: number
  in_stock: boolean
}

export interface Product {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  price: number
  image_url: string
  sizes: SizeStock[]
  in_stock: boolean
  /** Units on hand across all sizes (live inventory from the API). */
  total_in_stock: number
  /** Reviewed AI-generated on-model photo, if any (Problem 10). */
  model_image_url?: string | null
}

export interface CartItem {
  product_id: string
  name: string
  price: number
  image_url: string
  size: string
  qty: number
  /** Units in stock for this size; the cart never allows more than this. 0 = sold out since saved. */
  maxQty: number
}

export interface User {
  id: number
  firstName: string
  lastName: string
  email: string
}

/** Product match from the agent, rendered as a card (built server-side from the DB). */
export interface ChatProductCard {
  product_id: string
  name: string
  price: number
  image_url: string
  short_info: string
  garment_type: string
  stock_status: 'in_stock' | 'partly_sold_out' | 'sold_out'
  in_stock_sizes: string[]
  out_of_stock_sizes: string[]
}

/** The catalogue search behind a chat reply; replayed by the Products page ("View all"). */
export interface ChatSearch {
  query: string
  max_price: number | null
  size: string | null
  total_matches: number
}

/** POST /api/chat response. */
export interface ChatReply {
  reply: string
  products: ChatProductCard[]
  search: ChatSearch | null
  /** True when the exchange was saved to the logged-in shopper's account. */
  saved: boolean
}

/** One saved message from GET /api/chat/history (oldest first). */
export interface ChatHistoryMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  /** UTC "YYYY-MM-DD HH:MM:SS" */
  created_at: string
  products: ChatProductCard[]
  search: ChatSearch | null
}

/** What's on screen, sent with each chat message so "this" can be resolved. */
export interface PageContext {
  path: string
  page: 'home' | 'products' | 'search' | 'other'
  viewing_product_id: string | null
  last_viewed_product_id: string | null
  search_query: string | null
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}
