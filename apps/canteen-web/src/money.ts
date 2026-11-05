/** ₹40 for whole rupees, ₹40.50 otherwise. Amounts always arrive as integer paise. */
export function rupees(paise: number): string {
  const sign = paise < 0 ? '-' : ''
  const abs = Math.abs(paise)
  const fraction = abs % 100
  return `${sign}₹${Math.floor(abs / 100)}${fraction ? '.' + String(fraction).padStart(2, '0') : ''}`
}
