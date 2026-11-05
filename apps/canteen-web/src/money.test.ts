import { describe, expect, it } from 'vitest'
import { rupees } from './money'

describe('rupees', () => {
  it('formats paise', () => {
    expect(rupees(4000)).toBe('₹40')
    expect(rupees(4050)).toBe('₹40.50')
    expect(rupees(5)).toBe('₹0.05')
    expect(rupees(-8000)).toBe('-₹80')
  })
})
