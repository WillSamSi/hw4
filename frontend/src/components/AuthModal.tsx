import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { ApiError } from '../api'
import { useAuth } from '../context/AuthContext'
import { AlertIcon, CheckIcon, CloseIcon, EyeIcon, EyeOffIcon } from './Icons'
import Overlay from './Overlay'
import { PROMO } from '../store'

export type AuthMode = 'login' | 'register'

interface Props {
  mode: AuthMode
  onSwitch: (mode: AuthMode) => void
  /** Opened from the sign-up offer: mention the first-purchase discount. */
  promo?: boolean
  onClose: () => void
}

type FieldName = 'firstName' | 'lastName' | 'email' | 'password' | 'confirmPassword'
type Status = 'idle' | 'valid' | 'invalid'

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

// Shown under the password box; must match PASSWORD_RULES in backend/auth.py.
const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (p: string) => p.length >= 8 },
  { label: 'One uppercase letter (A–Z)', test: (p: string) => /[A-Z]/.test(p) },
  { label: 'One lowercase letter (a–z)', test: (p: string) => /[a-z]/.test(p) },
  { label: 'One number (0–9)', test: (p: string) => /\d/.test(p) },
  { label: 'One special character (e.g. ! @ # $ %)', test: (p: string) => /[^A-Za-z0-9]/.test(p) },
]

// Server error field names → form field names.
const SERVER_FIELDS: Record<string, FieldName> = {
  first_name: 'firstName',
  last_name: 'lastName',
  email: 'email',
  password: 'password',
  confirm_password: 'confirmPassword',
}

const empty = { firstName: '', lastName: '', email: '', password: '', confirmPassword: '' }

export default function AuthModal({ mode, onSwitch, onClose, promo = false }: Props) {
  const { login, register } = useAuth()
  const [form, setForm] = useState(empty)
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({})
  const [submitted, setSubmitted] = useState(false)
  const [serverErrors, setServerErrors] = useState<Partial<Record<FieldName, string>>>({})
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const formId = useId()
  const isLogin = mode === 'login'

  // ----- Validation -----
  const fields: FieldName[] = isLogin ? ['email', 'password'] : ['firstName', 'lastName', 'email', 'password', 'confirmPassword']

  const problem = (name: FieldName): string | null => {
    const v = form[name]
    if (serverErrors[name]) return serverErrors[name]!
    if (!v.trim()) return 'This field is required.'
    if (name === 'email' && !EMAIL_RE.test(v.trim())) return 'Enter a valid email address.'
    if (name === 'password' && !isLogin && !PASSWORD_RULES.every((r) => r.test(v)))
      return 'Password doesn’t meet all the rules below.'
    if (name === 'confirmPassword' && v !== form.password) return 'Passwords don’t match.'
    return null
  }

  const status = (name: FieldName): Status => {
    const err = problem(name)
    if (!err) return 'valid'
    const shown = submitted || touched[name] || !!serverErrors[name]
    // A mismatched confirmation turns red as soon as something is typed.
    if (name === 'confirmPassword' && form.confirmPassword) return 'invalid'
    return shown ? 'invalid' : 'idle'
  }

  const set = (name: FieldName) => (value: string) => {
    setForm((f) => ({ ...f, [name]: value }))
    setServerErrors((e) => ({ ...e, [name]: undefined }))
    setFormError('')
  }
  const blur = (name: FieldName) => () => setTouched((t) => ({ ...t, [name]: true }))

  // ----- Submit -----
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    const firstBad = fields.find((f) => problem(f))
    if (firstBad) {
      document.getElementById(`${formId}-${firstBad}`)?.focus()
      return // blocked: required fields are empty or invalid
    }
    setBusy(true)
    try {
      if (isLogin) await login(form.email.trim(), form.password)
      else await register({ ...form, email: form.email.trim() })
      onClose()
    } catch (err) {
      if (err instanceof ApiError) {
        const mapped: Partial<Record<FieldName, string>> = {}
        for (const [k, msg] of Object.entries(err.fields)) if (SERVER_FIELDS[k]) mapped[SERVER_FIELDS[k]] = msg
        setServerErrors(mapped)
        setFormError(Object.keys(mapped).length ? '' : err.message)
      } else {
        setFormError('Could not reach the server. Please try again.')
      }
    } finally {
      setBusy(false)
    }
  }

  const switchMode = () => {
    setSubmitted(false)
    setTouched({})
    setServerErrors({})
    setFormError('')
    setForm((f) => ({ ...empty, email: f.email }))
    onSwitch(isLogin ? 'register' : 'login')
  }

  const field = (name: FieldName, label: string, extra: Partial<FieldProps> = {}) => (
    <Field
      id={`${formId}-${name}`}
      label={label}
      value={form[name]}
      onChange={set(name)}
      onBlur={blur(name)}
      status={status(name)}
      error={status(name) === 'invalid' ? problem(name) : null}
      {...extra}
    />
  )

  return (
    <Overlay onClose={onClose} label={isLogin ? 'Log in' : 'Create account'}>
      <form className="auth-modal" onSubmit={submit} noValidate>
        <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
          <CloseIcon />
        </button>
        <h2>{isLogin ? 'Welcome Back' : 'Join Campus Customs'}</h2>
        <p className="muted">
          {isLogin
            ? 'Log in to pick up your saved cart.'
            : promo
              ? `Create an account to save your cart and get ${PROMO.percent}% off your first purchase.`
              : 'Create an account to save your cart for later.'}
        </p>

        {!isLogin && (
          <div className="form-row">
            {field('firstName', 'First Name', { autoComplete: 'given-name' })}
            {field('lastName', 'Last Name', { autoComplete: 'family-name' })}
          </div>
        )}
        {field('email', 'Email', { type: 'email', autoComplete: 'email' })}
        {field('password', 'Password', {
          secret: true,
          autoComplete: isLogin ? 'current-password' : 'new-password',
          hint: !isLogin && (
            <ul className="pw-rules" aria-label="Password rules">
              {PASSWORD_RULES.map((r) => {
                const met = r.test(form.password)
                const failed = !met && (submitted || touched.password)
                return (
                  <li key={r.label} className={met ? 'met' : failed ? 'failed' : ''}>
                    <span aria-hidden="true">{met ? '✓' : failed ? '✕' : '•'}</span> {r.label}
                  </li>
                )
              })}
            </ul>
          ),
        })}
        {!isLogin && field('confirmPassword', 'Confirm Password', { secret: true, autoComplete: 'new-password' })}

        {formError && (
          <p className="form-error" role="alert">
            {formError}
          </p>
        )}

        <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
          {busy ? 'Please wait…' : isLogin ? 'Log In' : 'Create Account'}
        </button>
        <p className="auth-switch">
          {isLogin ? "Don't have an account? " : 'Already have an account? '}
          <button type="button" className="link-btn link-btn--underline" onClick={switchMode}>
            {isLogin ? 'Create one' : 'Log in'}
          </button>
        </p>
      </form>
    </Overlay>
  )
}

interface FieldProps {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  onBlur: () => void
  status: Status
  error: string | null
  type?: string
  autoComplete?: string
  /** Password-style field: hidden by default with a show/hide toggle. */
  secret?: boolean
  hint?: ReactNode
}

function Field({ id, label, value, onChange, onBlur, status, error, type = 'text', autoComplete, secret, hint }: FieldProps) {
  const [visible, setVisible] = useState(false)
  return (
    <div className={`field field--${status}`}>
      <label htmlFor={id}>{label}</label>
      <div className="field__control">
        <input
          id={id}
          type={secret && !visible ? 'password' : secret ? 'text' : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          autoComplete={autoComplete}
          aria-invalid={status === 'invalid'}
          aria-describedby={error ? `${id}-error` : undefined}
          required
        />
        {secret && (
          <button
            type="button"
            className="field__toggle"
            aria-label={visible ? 'Hide password' : 'Show password'}
            aria-pressed={visible}
            onClick={() => setVisible((v) => !v)}
          >
            {visible ? <EyeOffIcon size={20} /> : <EyeIcon size={20} />}
          </button>
        )}
        <span className="field__status" aria-hidden="true">
          {status === 'valid' && <CheckIcon size={16} />}
          {status === 'invalid' && <AlertIcon size={16} />}
        </span>
      </div>
      {error && (
        <p className="field__error" id={`${id}-error`}>
          {error}
        </p>
      )}
      {hint}
    </div>
  )
}
