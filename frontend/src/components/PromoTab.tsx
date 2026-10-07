import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useViewing } from '../context/ProductModalContext'
import { PROMO } from '../store'
import AuthModal, { type AuthMode } from './AuthModal'
import { CloseIcon } from './Icons'

const SHOW_ON = ['/', '/products']
const DISMISS_KEY = 'cc-promo-dismissed'

/** Floating sign-up offer on the right edge (Home + Products only).
 *  Hidden for logged-in shoppers, while a product pop-up is open, and after it's dismissed this visit. */
export default function PromoTab() {
  const { pathname } = useLocation()
  const { user, ready } = useAuth()
  const { current } = useViewing()
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem(DISMISS_KEY) === '1')
  const [authMode, setAuthMode] = useState<AuthMode | null>(null)

  const visible = ready && !user && !dismissed && !current && !authMode && SHOW_ON.includes(pathname)

  const dismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, '1')
    setDismissed(true)
  }

  return (
    <>
      {visible && (
        <aside className="promo-tab" aria-label="Sign-up offer">
          <button className="promo-tab__body" onClick={() => setAuthMode('register')}>
            <span className="promo-tab__badge">{PROMO.percent}% OFF</span>
            <span className="promo-tab__text">{PROMO.label}</span>
            <span className="promo-tab__cta">Sign up →</span>
          </button>
          <button className="promo-tab__close" aria-label="Dismiss offer" onClick={dismiss}>
            <CloseIcon size={14} />
          </button>
        </aside>
      )}
      {authMode && (
        <AuthModal mode={authMode} onSwitch={setAuthMode} onClose={() => setAuthMode(null)} promo />
      )}
    </>
  )
}
