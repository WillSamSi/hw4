import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { formatPrice } from '../api'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'
import AuthModal, { type AuthMode } from './AuthModal'
import { CartIcon, CloseIcon, UserIcon } from './Icons'

/** Closes a dropdown when the user clicks anywhere outside it. */
function useClickOutside(onOutside: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onOutside()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onOutside])
  return ref
}

export default function NavBar() {
  const { pathname, hash } = useLocation()
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const aboutActive = pathname === '/' && hash === '#about'

  return (
    <header className={`navbar${scrolled ? ' navbar--scrolled' : ''}`}>
      <div className="navbar__inner">
        <Link to="/" className="brand" aria-label="Yale Campus Customs home">
          <span className="brand__yale">Yale</span>
          <span className="brand__name">
            Campus
            <br />
            Customs
          </span>
        </Link>

        <nav className="navbar__links" aria-label="Main">
          <NavLink to="/" end className={() => (pathname === '/' && !aboutActive ? 'active' : '')}>
            Home
          </NavLink>
          <NavLink to="/products">Products</NavLink>
          <Link to="/#about" className={aboutActive ? 'active' : ''}>
            About Us
          </Link>
        </nav>

        <div className="navbar__actions">
          <CartMenu />
          <ProfileMenu />
        </div>
      </div>
    </header>
  )
}

function CartMenu() {
  const { items, count, subtotal, setQty, remove } = useCart()
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useClickOutside(() => setOpen(false))

  return (
    <div className="menu" ref={ref}>
      <button
        className="icon-btn"
        aria-label={`Cart, ${count} item${count === 1 ? '' : 's'}`}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <CartIcon />
        {count > 0 && <span className="badge">{count}</span>}
      </button>

      {open && (
        <div className="dropdown cart-dropdown" role="dialog" aria-label="Your cart">
          <h3 className="dropdown__title">Your Cart</h3>
          {!user && items.length > 0 && <p className="cart-hint">Log in to save this cart to your account.</p>}
          {items.length === 0 ? (
            <p className="muted">Your cart is empty. Time to gear up!</p>
          ) : (
            <>
              <ul className="cart-list">
                {items.map((i) => (
                  <li key={`${i.product_id}-${i.size}`} className={`cart-item${i.maxQty === 0 ? ' cart-item--soldout' : ''}`}>
                    <img src={i.image_url} alt="" />
                    <div className="cart-item__info">
                      <strong>{i.name}</strong>
                      <span className="muted">Size {i.size}</span>
                      {i.maxQty === 0 && <span className="soldout-note">Sold out for now — not in your total</span>}
                      <div className="qty">
                        <button aria-label="Decrease quantity" onClick={() => setQty(i.product_id, i.size, i.qty - 1)}>
                          −
                        </button>
                        <span>{i.qty}</span>
                        <button
                          aria-label="Increase quantity"
                          disabled={i.maxQty === 0 || i.qty >= i.maxQty}
                          onClick={() => setQty(i.product_id, i.size, i.qty + 1)}
                        >
                          +
                        </button>
                      </div>
                    </div>
                    <div className="cart-item__right">
                      <span>{formatPrice(i.price * i.qty)}</span>
                      <button className="link-btn" aria-label={`Remove ${i.name}`} onClick={() => remove(i.product_id, i.size)}>
                        <CloseIcon size={16} />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="cart-total">
                <span>Subtotal</span>
                <strong>{formatPrice(subtotal)}</strong>
              </div>
              <button className="btn btn--primary btn--block" disabled title="Checkout is coming soon">
                Checkout — Coming Soon
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function ProfileMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [authMode, setAuthMode] = useState<AuthMode | null>(null)
  const ref = useClickOutside(() => setOpen(false))

  const openAuth = (mode: AuthMode) => {
    setOpen(false)
    setAuthMode(mode)
  }

  return (
    <div className="menu" ref={ref}>
      <button className="profile-btn" aria-expanded={open} aria-label="Account menu" onClick={() => setOpen((o) => !o)}>
        <span className="icon-btn icon-btn--static">
          <UserIcon />
        </span>
        {user && <span className="profile-btn__name">Hi, {user.firstName}</span>}
      </button>

      {open && (
        <div className="dropdown profile-dropdown" role="menu">
          {user ? (
            <>
              <button role="menuitem" className="dropdown__item" disabled>
                Profile <span className="soon">Soon</span>
              </button>
              <button role="menuitem" className="dropdown__item" disabled>
                Account Settings <span className="soon">Soon</span>
              </button>
              <button
                role="menuitem"
                className="dropdown__item"
                onClick={() => {
                  setOpen(false)
                  void logout()
                }}
              >
                Log Out
              </button>
            </>
          ) : (
            <>
              <button role="menuitem" className="dropdown__item" onClick={() => openAuth('login')}>
                Log In
              </button>
              <button role="menuitem" className="dropdown__item" onClick={() => openAuth('register')}>
                Create Account
              </button>
            </>
          )}
        </div>
      )}

      {authMode && <AuthModal mode={authMode} onSwitch={setAuthMode} onClose={() => setAuthMode(null)} />}
    </div>
  )
}
