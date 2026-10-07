// Inline stroke icons (24×24) so the app has no icon-font dependency.
type IconProps = { size?: number }

const base = (size = 22) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
})

export const CartIcon = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M5 8h14l-1.2 11.2a2 2 0 0 1-2 1.8H8.2a2 2 0 0 1-2-1.8L5 8Z" />
    <path d="M9 8V6a3 3 0 0 1 6 0v2" />
  </svg>
)

export const UserIcon = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
  </svg>
)

export const ChatIcon = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M21 12a8.5 8.5 0 0 1-12.6 7.4L3 21l1.6-5.2A8.5 8.5 0 1 1 21 12Z" />
  </svg>
)

export const CloseIcon = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
)

export const SendIcon = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M4 12 20 4l-6 16-3-7-7-1Z" />
  </svg>
)

export const ChevronLeft = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="m15 6-6 6 6 6" />
  </svg>
)

export const ChevronRight = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="m9 6 6 6-6 6" />
  </svg>
)

export const EyeIcon = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
)

export const EyeOffIcon = ({ size }: IconProps) => (
  <svg {...base(size)}>
    <path d="M10.6 5.1A10.6 10.6 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.1M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6" />
    <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2M3 3l18 18" />
  </svg>
)

export const CheckIcon = ({ size }: IconProps) => (
  <svg {...base(size)} strokeWidth={2.6}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </svg>
)

export const AlertIcon = ({ size }: IconProps) => (
  <svg {...base(size)} strokeWidth={2.4}>
    <path d="M12 7v6M12 17h.01" />
  </svg>
)
