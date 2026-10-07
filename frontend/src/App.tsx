import { useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import ChatWidget from './components/ChatWidget'
import Footer from './components/Footer'
import NavBar from './components/NavBar'
import PromoTab from './components/PromoTab'
import { AuthProvider, useAuth } from './context/AuthContext'
import { CartProvider } from './context/CartContext'
import { ProductModalProvider } from './context/ProductModalContext'
import Home from './pages/Home'
import Products from './pages/Products'

function ScrollToTop() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    if (!hash) window.scrollTo({ top: 0 })
  }, [pathname, hash])
  return null
}

/** New conversation whenever the account changes, so one shopper never sees another's chat. */
function ChatHost() {
  const { user } = useAuth()
  return <ChatWidget key={user?.id ?? 'guest'} />
}

export default function App() {
  return (
    <AuthProvider>
      <CartProvider>
        <ProductModalProvider>
          <ScrollToTop />
          <NavBar />
          <main>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/products" element={<Products />} />
              <Route path="*" element={<Home />} />
            </Routes>
          </main>
          <Footer />
          <PromoTab />
          <ChatHost />
        </ProductModalProvider>
      </CartProvider>
    </AuthProvider>
  )
}
