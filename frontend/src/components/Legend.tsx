interface Entry {
  term: string
  definition: string
  formula?: string
}

const ENTRIES: Entry[] = [
  {
    term: 'Strike',
    definition:
      'The price at which you agree to buy the stock if the option is exercised. Lower strike = further from current price = safer.',
  },
  {
    term: 'Premium',
    definition:
      'The money you collect upfront for selling the put option. This is your profit if the option expires worthless.',
    formula: 'Premium = (Bid + Ask) / 2',
  },
  {
    term: 'POP (Probability of Profit)',
    definition:
      'The chance the option expires worthless and you keep the full premium. Higher = safer.',
    formula: 'POP = 1 - |Delta|',
  },
  {
    term: 'Delta',
    definition:
      'How sensitive the option price is to stock movement. For puts, delta ranges from 0 to -1. A delta of -0.20 means roughly a 20% chance of assignment.',
  },
  {
    term: 'Theta',
    definition:
      'How much value the option loses each day due to time decay. As a put seller, theta works in your favor — the option gets cheaper over time.',
  },
  {
    term: 'IV (Implied Volatility)',
    definition:
      'How much the market expects the stock to move. Higher IV = richer premiums but more risk. Lower IV = calmer stock.',
  },
  {
    term: 'EV (Expected Value)',
    definition:
      'The average dollar outcome per contract if you made this trade many times. Positive EV = profitable over time.',
    formula: 'EV = (POP × Premium × 100) - ((1 - POP) × Expected Loss × 100)',
  },
  {
    term: 'Expected Loss',
    definition:
      'The max loss if the stock drops to the support level. This is the downside used in the EV calculation.',
    formula: 'Expected Loss = Strike - Support Level',
  },
  {
    term: 'Support Level',
    definition:
      'A price floor where the stock has historically bounced back up. Found by detecting local minima in the last 60 days of price data.',
  },
  {
    term: 'Premium Yield',
    definition:
      'The annualized return on the capital at risk (the strike price). Lets you compare trades with different strikes and expiries.',
    formula: 'Yield = (Premium / Strike) × (365 / Days to Expiry)',
  },
  {
    term: 'Safety Score',
    definition:
      'A composite risk score from 0 (risky) to 1 (very safe), based on six weighted factors.',
    formula:
      '25% Distance from Support + 20% Put/Call Flow + 15% Pre-Market Stability + 15% IV Rank + 15% Market Risk (VIX) + 10% SPY Correlation',
  },
  {
    term: 'Adjusted Score',
    definition:
      'The final ranking metric. Rewards trades that are both high-EV and safe. Higher = better. This is not a percentage — it is a relative score for comparing trades.',
    formula: 'Adjusted Score = EV × (1 + Safety Score)',
  },
  {
    term: 'OTM (Out of the Money)',
    definition:
      'A put is OTM when the strike is below the current stock price. The further OTM, the less likely assignment. All trades shown are OTM.',
  },
  {
    term: 'VIX',
    definition:
      'The "fear index" — measures expected market volatility. Below 20 = calm, above 25 = stressed. When elevated, the screener reduces the number of recommended trades.',
  },
]

interface Props {
  onClose: () => void
}

export default function Legend({ onClose }: Props) {
  return (
    <div className="border-b border-terminal-border bg-terminal-surface/80 px-4 py-4 max-h-[70vh] overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-terminal-yellow uppercase tracking-wider">
          Legend
        </h3>
        <button
          onClick={onClose}
          className="text-terminal-muted hover:text-terminal-text text-sm"
        >
          Close
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        {ENTRIES.map((entry) => (
          <div
            key={entry.term}
            className="border border-terminal-border/50 rounded px-3 py-2"
          >
            <div className="font-bold text-terminal-cyan text-xs uppercase tracking-wider mb-1">
              {entry.term}
            </div>
            <p className="text-terminal-text text-xs leading-relaxed">
              {entry.definition}
            </p>
            {entry.formula && (
              <p className="mt-1 text-terminal-yellow text-xs font-mono">
                {entry.formula}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
