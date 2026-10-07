import { Fragment, useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'
import { ApiError, clearChatHistory, fetchChatHistory, fetchProduct, formatPrice, searchParamsFor, sendChat } from '../api'
import { useAuth } from '../context/AuthContext'
import { useOpenProduct, useViewing } from '../context/ProductModalContext'
import type { ChatHistoryMessage, ChatProductCard, ChatSearch, ChatTurn, PageContext } from '../types'
import { ChatIcon, CloseIcon, SendIcon } from './Icons'

// Must match the backend's MAX_MESSAGE_CHARS / MAX_HISTORY_TURN_CHARS (backend/config.py).
const MAX_MESSAGE_CHARS = 1000
const MAX_HISTORY_TURN_CHARS = 2000

interface Message {
  id: number
  role: 'user' | 'assistant'
  text: string
  time: string
  /** Day label for the date chips ("Today", "Yesterday", "Sep 19"). */
  day: string
  products?: ChatProductCard[]
  search?: ChatSearch | null
  /** Local-only messages (greeting, errors) aren't sent back to the agent as history. */
  local?: boolean
  /** The opening greeting; its text follows who is logged in. */
  greeting?: boolean
}

const HISTORY_TURNS = 10
let nextId = 1

const timeOf = (d: Date) => d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
const dayOf = (d: Date) => {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  if (d.toDateString() === today.toDateString()) return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: d.getFullYear() === today.getFullYear() ? undefined : 'numeric' })
}
const stamp = (d = new Date()) => ({ time: timeOf(d), day: dayOf(d) })

/** Saved message (UTC timestamp from SQLite) → widget message. */
const fromHistory = (m: ChatHistoryMessage): Message => ({
  id: nextId++,
  role: m.role,
  text: m.content,
  ...stamp(new Date(m.created_at.replace(' ', 'T') + 'Z')),
  products: m.products,
  search: m.search,
})

const greetingText = (firstName?: string, returning = false) =>
  returning
    ? `Welcome back, ${firstName}! 👋 Your earlier chats are saved above. What can I help you find today?`
    : `Hey ${firstName ?? 'Bulldog'}! 👋 I'm the Campus Customs assistant. Ask me about products, sizes, stock, or our store hours.`

const greeting = (): Message => ({ id: nextId++, role: 'assistant', text: '', ...stamp(), local: true, greeting: true })

/** Floating WhatsApp-style chat with the PydanticAI shop agent (POST /api/chat). */
export default function ChatWidget() {
  const { user } = useAuth()
  const openProduct = useOpenProduct()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const { pathname, search: queryString } = useLocation()
  const viewing = useViewing()
  const [messages, setMessages] = useState<Message[]>(() => [greeting()])
  const [returning, setReturning] = useState(false)

  // Logged in → reload the saved conversation (the widget remounts whenever the account changes).
  useEffect(() => {
    if (!user) return
    let cancelled = false
    fetchChatHistory()
      .then((saved) => {
        if (cancelled || saved.length === 0) return
        setReturning(true)
        setMessages((m) => [...saved.map(fromHistory), ...m.filter((x) => x.greeting), ...m.filter((x) => !x.greeting)])
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [user])

  /** Page context so the agent can resolve "this one" (validated again on the server). */
  const pageContext = (): PageContext => {
    const params = new URLSearchParams(queryString)
    const q = params.get('q')
    return {
      path: pathname + queryString,
      page: pathname === '/' ? 'home' : pathname === '/products' ? (q ? 'search' : 'products') : 'other',
      viewing_product_id: viewing.current?.product_id ?? null,
      last_viewed_product_id: viewing.lastViewed?.product_id ?? null,
      search_query: q,
    }
  }

  const clearHistory = async () => {
    if (!window.confirm('Delete your saved chat history? This can’t be undone.')) return
    try {
      await clearChatHistory()
      setReturning(false)
      setMessages([greeting()])
    } catch {
      /* keep messages if the server refused */
    }
  }
  const [draft, setDraft] = useState('')
  const [typing, setTyping] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, typing, open])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  /** Sends a message (typed or from a chip) to the agent. */
  const sendText = async (raw: string) => {
    const text = raw.trim()
    if (!text || typing) return
    const history: ChatTurn[] = messages
      .filter((m) => !m.local)
      .slice(-HISTORY_TURNS)
      .map((m) => ({ role: m.role, content: m.text.slice(0, MAX_HISTORY_TURN_CHARS) }))
    setDraft('')
    setMessages((m) => [...m, { id: nextId++, role: 'user', text, ...stamp() }])
    setTyping(true)
    try {
      const { reply, products, search } = await sendChat(text, history, pageContext())
      setMessages((m) => [...m, { id: nextId++, role: 'assistant', text: reply, ...stamp(), products, search }])
    } catch (err) {
      const msg =
        err instanceof ApiError && err.status === 422
          ? `Sorry, I couldn't read that message. Please keep it under ${MAX_MESSAGE_CHARS.toLocaleString()} characters.`
          : err instanceof ApiError
            ? err.message
            : "Sorry, I couldn't reach the server. Please try again."
      setMessages((m) => [...m, { id: nextId++, role: 'assistant', text: msg, ...stamp(), local: true }])
    } finally {
      setTyping(false)
      inputRef.current?.focus()
    }
  }

  const send = (e: FormEvent) => {
    e.preventDefault()
    void sendText(draft)
  }

  // Enter sends; Shift+Enter adds a new line (and IME composition is never interrupted).
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void sendText(draft)
    }
  }

  // Grow the message box with its content, up to ~5 lines.
  useLayoutEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }, [draft, open])

  const lastMessage = messages[messages.length - 1]
  const chips =
    !typing && lastMessage?.role === 'assistant'
      ? suggestionChips({
          viewing: viewing.current?.name ?? null,
          lastReply: lastMessage,
          loggedIn: Boolean(user),
          lastAsked: [...messages].reverse().find((m) => m.role === 'user')?.text ?? '',
        })
      : []

  const showProduct = async (productId: string) => {
    try {
      const product = await fetchProduct(productId)
      setOpen(false) // tuck the chat away so the pop-up is fully visible; the conversation is kept
      openProduct(product)
    } catch {
      /* ignore: card stays as-is */
    }
  }

  /** "View all" replays the agent's search on the Products page (same engine, full result set). */
  const viewAll = (search: ChatSearch) => {
    setOpen(false)
    navigate(`/products?${searchParamsFor(search)}`)
  }

  // Portal to <body> so the chat always sits above every page and pop-up.
  return createPortal(
    <div className="chat-root">
      {open && (
        <section className="chat-panel" aria-label="Chat with Campus Customs">
          <header className="chat-header">
            <div className="chat-avatar" aria-hidden="true">
              Y
            </div>
            <div className="chat-header__text">
              <strong>Campus Customs Assistant</strong>
              <span>{typing ? 'typing…' : user ? 'online · chat saved' : 'online'}</span>
            </div>
            {user && (
              <button className="chat-header__clear" onClick={clearHistory} title="Delete saved chat history">
                Clear
              </button>
            )}
            <button className="chat-header__close" aria-label="Close chat" onClick={() => setOpen(false)}>
              <CloseIcon size={20} />
            </button>
          </header>

          <div className="chat-body" ref={bodyRef} aria-live="polite">
            {messages.map((m, i) => (
              <Fragment key={m.id}>
                {(i === 0 || messages[i - 1].day !== m.day) && <span className="chat-day">{m.day}</span>}
                <div className={`bubble bubble--${m.role === 'user' ? 'out' : 'in'}`}>
                  <div className="bubble__text">
                     {m.greeting ? greetingText(user?.firstName, returning) : m.role === 'assistant' ? <RichText text={m.text} /> : m.text}
                  </div>
                  <span className="bubble__meta">
                    {m.time}
                    {m.role === 'user' && <span className="ticks">✓✓</span>}
                  </span>
                </div>
                {m.products && m.products.length > 0 && (
                  <div className="chat-results">
                    <div className="chat-cards">
                      {m.products.map((p) => (
                        <button key={p.product_id} className="chat-card" onClick={() => showProduct(p.product_id)}>
                          <span className="chat-card__image">
                            <img src={p.image_url} alt="" loading="lazy" />
                            {p.stock_status === 'sold_out' && <span className="chat-card__tag">Sold out</span>}
                          </span>
                          <span className="chat-card__name">{p.name}</span>
                          <span className="chat-card__price">{formatPrice(p.price)}</span>
                          <span className="chat-card__info">{p.short_info}</span>
                          <span className="chat-card__sizes">
                            {p.stock_status === 'sold_out'
                              ? 'Sold out in every size for now'
                              : p.out_of_stock_sizes.length
                                ? `Sold out: ${p.out_of_stock_sizes.join(', ')}`
                                : 'All sizes in stock'}
                          </span>
                        </button>
                      ))}
                    </div>
                    {m.search && (
                      <button className="chat-viewall" onClick={() => viewAll(m.search!)}>
                        {m.search.total_matches > m.products.length
                          ? `View all ${m.search.total_matches} matches on the page →`
                          : 'Show these on the page →'}
                      </button>
                    )}
                  </div>
                )}
              </Fragment>
            ))}
            {typing && (
              <div className="bubble bubble--in bubble--typing" role="status" aria-label="Campus Customs is typing">
                <span />
                <span />
                <span />
                <em>Campus Customs is typing…</em>
              </div>
            )}
          </div>

          {chips.length > 0 && (
            <div className="chat-chips" aria-label="Suggested questions">
              {chips.map((c) => (
                <button key={c} type="button" className="chat-chip" onClick={() => void sendText(c)}>
                  {c}
                </button>
              ))}
            </div>
          )}

          <form className="chat-input" onSubmit={send}>
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Type a message"
              aria-label="Message (Enter to send, Shift+Enter for a new line)"
              maxLength={MAX_MESSAGE_CHARS}
            />
            <button type="submit" className="chat-send" aria-label="Send" disabled={!draft.trim() || typing}>
              <SendIcon size={20} />
            </button>
          </form>
        </section>
      )}

      <button
        className={`chat-fab${open ? ' chat-fab--open' : ''}`}
        aria-label={open ? 'Close chat' : 'Open chat'}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <CloseIcon size={26} /> : <ChatIcon size={28} />}
      </button>
    </div>,
    document.body,
  )
}

/** Renders the agent's light markdown (**bold** and "- " bullets) without injecting HTML. */
function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let bullets: string[] = []
  const flush = () => {
    if (bullets.length) blocks.push(<ul key={blocks.length}>{bullets.map((b, i) => <li key={i}>{inline(b)}</li>)}</ul>)
    bullets = []
  }
  for (const line of text.split('\n')) {
    const bullet = line.match(/^\s*[-•*]\s+(.*)$/)
    if (bullet) {
      bullets.push(bullet[1])
      continue
    }
    flush()
    if (line.trim()) blocks.push(<p key={blocks.length}>{inline(line)}</p>)
  }
  flush()
  return <>{blocks}</>
}

const inline = (s: string) =>
  s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )

interface ChipContext {
  /** Name of the product whose pop-up is open, if any. */
  viewing: string | null
  lastReply: Message
  loggedIn: boolean
  lastAsked: string
}

/** 3–4 suggested next questions, based on what the shopper is looking at and the last reply. */
function suggestionChips({ viewing, lastReply, loggedIn, lastAsked }: ChipContext): string[] {
  const cards = lastReply.products ?? []
  let chips: string[]
  if (viewing) {
    // On a product page (pop-up open): every chip is about that product.
    chips = [
      `Is the ${viewing} in stock in M?`,
      `What colors does the ${viewing} come in?`,
      `Show me items similar to the ${viewing}`,
      `How much is the ${viewing}?`,
    ]
  } else if (lastReply.search && cards.length > 1) {
    // After search results: refine them.
    chips = ['Which of these are under $50?', 'Do any of these come in XL?', 'Show me the gray ones', 'Gifts under $50']
  } else if (cards.length >= 1) {
    // After a reply about specific items: follow up on the first one.
    const name = cards[0].name
    chips = [`Is the ${name} in stock in M?`, `What colors does the ${name} come in?`, 'Show me similar items', 'Gifts under $50']
  } else if (loggedIn) {
    chips = ["What's in my cart?", 'What hoodies do you have?', 'Gifts under $50', 'When are you open?']
  } else {
    chips = ['What hoodies do you have?', 'Gifts under $50', 'Quarter-zips in size M?', 'When are you open?']
  }
  // Drop the question just asked; product chips are long, so show 3 of them, otherwise up to 4.
  return chips.filter((c) => c.toLowerCase() !== lastAsked.trim().toLowerCase()).slice(0, viewing ? 3 : 4)
}
