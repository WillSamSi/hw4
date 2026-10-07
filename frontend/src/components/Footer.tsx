import { STORE } from '../store'

const YEAR = new Date().getFullYear()

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer__inner">
        <div>
          <span className="brand__yale brand__yale--light">Yale</span>
          <p>
            {STORE.name} · {STORE.address}
          </p>
        </div>
        <p className="footer__copy">© {YEAR} Yale Campus Customs. Boola Boola!</p>
      </div>
    </footer>
  )
}
