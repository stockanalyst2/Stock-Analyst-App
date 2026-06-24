# Stock Options Opportunity Scoring Engine

## Objective

Analyze individual stocks and determine whether purchasing a call or put option currently offers favorable probability, liquidity, volatility characteristics, and risk/reward.

The system is NOT a generic trading glossary.

The system IS an options opportunity ranking engine.

---

## Primary Outputs

- Call Score (0-100)
- Put Score (0-100)
- Confidence Score (0-100)
- Thesis Summary
- Risk Summary
- Invalidation Conditions
- Missing Data Warnings

---

## Scoring Weights

### Price Action (25%)

Evaluate:

- Trend
- BOS (Break of Structure)
- CHoCH (Change of Character)
- Relative Strength
- Relative Weakness
- Volume Expansion
- Volume Contraction
- Breakout
- Pullback
- Support
- Resistance
- Supply Zones
- Demand Zones
- ATR

---

### Options Chain Quality (20%)

Evaluate:

- Open Interest
- Contract Volume
- Bid/Ask Spread
- Liquidity
- Delta
- Gamma
- Theta
- Vega

---

### Options Flow (20%)

Evaluate:

- Call Sweeps
- Put Sweeps
- Block Trades
- Unusual Activity
- Dark Pool Prints

---

### Volatility Analysis (15%)

Evaluate:

- Implied Volatility
- IV Rank
- IV Percentile
- Realized Volatility
- Volatility Expansion
- Volatility Compression

---

### Market Context (10%)

Evaluate:

- Earnings Risk
- News Catalysts
- Analyst Upgrades
- Analyst Downgrades
- Sector Strength
- Sector Weakness
- Market Breadth
- VIX Environment

---

### Dealer Positioning (10%)

Evaluate:

- Gamma Exposure (GEX)
- Delta Exposure (DEX)
- Gamma Flip
- Call Wall
- Put Wall
- Vanna
- Charm

---

## Confidence Rules

Increase confidence when:

- Multiple categories agree
- Volume confirms price action
- Flow confirms price action
- Dealer positioning supports thesis
- Liquidity is strong

Decrease confidence when:

- Data is missing
- Signals conflict
- Liquidity is weak
- Event risk is elevated

---

## Hard Rules

Never infer:

- GEX
- DEX
- Vanna
- Charm
- Options Flow
- Dark Pool Activity
- Dealer Positioning

from OHLCV candles alone.

These require dedicated external data.

---

## Output Philosophy

The system produces:

- Observations
- Evidence
- Risk Assessment
- Confidence Assessment

The system does NOT produce financial advice.

The system must separate:

- Observation
- Interpretation
- Confidence
- Risk
- Invalidation
