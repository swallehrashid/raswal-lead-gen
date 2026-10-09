/** Kenyan phone helpers. */
export function normalizeKe(input: string): string | null {
  const raw = input.trim()
  const digits = raw.replace(/\D/g, '')
  if (raw.startsWith('+') && digits.length >= 10 && digits.length <= 15) return `+${digits}`
  if (digits.startsWith('254') && digits.length === 12) return `+${digits}`
  if (digits.startsWith('0') && digits.length === 10) return `+254${digits.slice(1)}`
  if (/^[17]\d{8}$/.test(digits)) return `+254${digits}`
  return null
}

export const waDigits = (e164: string) => e164.replace(/\D/g, '')

export function displayPhone(e164: string | null | undefined): string {
  if (!e164) return ''
  if (e164.startsWith('+254') && e164.length === 13) return `0${e164.slice(4, 7)} ${e164.slice(7, 10)} ${e164.slice(10)}`
  return e164
}

export const waPhoneLink = (e164: string) => `https://wa.me/${waDigits(e164)}`
export const waWebLink = (e164: string) => `https://web.whatsapp.com/send?phone=${waDigits(e164)}`
