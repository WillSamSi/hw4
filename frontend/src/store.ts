// Physical store details (from yalebulldogblue.com "Come Visit Us!").
export const STORE = {
  name: 'Campus Customs',
  street: '57 Broadway',
  city: 'New Haven, CT 06511',
  get address() {
    return `${this.street}, ${this.city}`
  },
  /** days: JS getDay() values (0 = Sunday) the row applies to, used to highlight today. */
  hours: [
    { label: 'Mon – Fri', time: '10 AM – 7 PM', days: [1, 2, 3, 4, 5] },
    { label: 'Sat – Sun', time: '10 AM – 2 PM', days: [0, 6] },
    { label: 'Holidays & Celebrations', time: '12 PM – 7 PM', days: [] as number[] },
  ],
}

const query = encodeURIComponent(`${STORE.name}, ${STORE.address}`)
export const MAPS_URL = `https://www.google.com/maps/search/?api=1&query=${query}`
// Direct embed URL (the short ?output=embed form redirects with X-Frame-Options: SAMEORIGIN).
export const MAPS_EMBED_URL = `https://www.google.com/maps/embed?origin=mfe&pb=!1m2!2m1!1s${query}`

/** Model photo bank in frontend/public/models/. */
export const MODEL_PHOTOS = {
  lifestyle: [
    { src: '/models/students-yale-hoodie.webp', position: 'center 30%' },
    { src: '/models/model-students-walking.jpg', position: 'center 35%' },
    { src: '/models/model-students-banner.jpg', position: 'center 20%' },
  ],
  lookbook: [
    '/models/model-bulldog-knit-1.jpg',
    '/models/model-bulldog-knit-2.jpg',
    '/models/model-bulldog-knit-3.jpg',
    '/models/model-bulldog-knit-4.jpg',
  ],
}

/** Sign-up offer shown on the floating promo label and in the Create Account pop-up.
 *  Page-only: the chat agent does not mention discounts. Checkout isn't live yet, so the
 *  discount is advertised now and applied once checkout launches. */
export const PROMO = {
  percent: 15,
  label: 'Sign up now, and receive 15% Off on your first purchase',
}
