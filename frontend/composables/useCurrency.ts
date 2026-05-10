const SYMBOLS: Record<string, string> = {
  USD: '$', EUR: '€', GBP: '£', JPY: '¥', CNY: '¥', HKD: 'HK$',
  AUD: 'A$', CAD: 'C$', CHF: 'CHF ', SGD: 'S$', TWD: 'NT$', KRW: '₩',
  INR: '₹', BRL: 'R$', MXN: 'MX$', ZAR: 'R', NGN: '₦', SEK: 'kr ',
  NOK: 'kr ', DKK: 'kr ', PLN: 'zł ', CZK: 'Kč ', HUF: 'Ft ', RUB: '₽',
  TRY: '₺', ARS: 'AR$', CLP: 'CLP$', COP: 'COP$', PEN: 'S/', IDR: 'Rp ',
  MYR: 'RM ', THB: '฿', VND: '₫', EGP: 'E£', SAR: 'SR ', AED: 'AED ',
  ILS: '₪', QAR: 'QR ', KWD: 'KD ', BHD: 'BD ', OMR: 'OR ', JOD: 'JD ',
  PKR: '₨', BDT: '৳', LKR: '₨', MAD: 'MAD ', TND: 'TND ', GHS: 'GH₵',
  KES: 'KSh ', UGX: 'USh ', TZS: 'TSh ', ZMW: 'K ',
}

// Currencies that show 0 decimal places
const NO_DECIMALS = new Set(['JPY', 'KRW', 'IDR', 'VND', 'HUF', 'CLP', 'COP'])

export function useCurrency() {
  function fmtPrice(v: number | null | undefined, currency?: string): string {
    if (v == null) return '—'
    const cur = (currency ?? 'USD').toUpperCase()

    // GBp = British pence (sub-currency)
    if (currency === 'GBp') return `${v.toFixed(2)}p`

    const sym = SYMBOLS[cur] ?? `${cur} `
    if (NO_DECIMALS.has(cur)) return `${sym}${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    if (v >= 10000) return `${sym}${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    if (v >= 1) return `${sym}${v.toFixed(2)}`
    return `${sym}${v.toFixed(4)}`
  }

  function fmtCap(v: number | null | undefined): string {
    if (!v) return '—'
    if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
    if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
    return `$${(v / 1e6).toFixed(0)}M`
  }

  function fmtUsd(v: number | null | undefined, signed = false): string {
    if (v == null) return '—'
    const sign = signed && v > 0 ? '+' : ''
    if (Math.abs(v) >= 1e12) return `${sign}$${(v / 1e12).toFixed(1)}T`
    if (Math.abs(v) >= 1e9)  return `${sign}$${(v / 1e9).toFixed(0)}B`
    if (Math.abs(v) >= 1e6)  return `${sign}$${(v / 1e6).toFixed(0)}M`
    return `${sign}$${v.toLocaleString()}`
  }

  return { fmtPrice, fmtCap, fmtUsd }
}
