// Display labels for the four QuantScore factors.
// API keys stay "profitability" and "growth"; what the user reads must say
// these are proxies (price-based ratios and price momentum), not fundamentals.
export const FACTOR_LABELS = {
  valuation: 'Valuation',
  profitability: 'Profitability (proxy)',
  growth: 'Growth (proxy: momentum)',
  dividend: 'Dividend',
}

export const FACTOR_SHORT = {
  valuation: 'Valuation',
  profitability: 'Profit (proxy)',
  growth: 'Momentum',
  dividend: 'Dividend',
}

export const PROXY_NOTE =
  'Profitability is a proxy (earnings yield, EBITDA / market cap). ' +
  'Growth is a proxy (1-year price return, 52-week range position), i.e. price momentum, ' +
  'not revenue or earnings growth.'
