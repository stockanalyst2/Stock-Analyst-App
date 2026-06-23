# Stock Market Analyst

A local Python stock screener that scans familiar high-liquidity stocks, applies options-trading setup rules, and returns short-term CALL/PUT candidates. The default strategy is reversal trading:

- CALL candidates: recent dips into support with signs of stabilization or rebound
- PUT candidates: recent spikes into resistance with signs of rejection or rollover
- Volume context: current volume versus 20-day average volume
- RSI context: washed-out rebounds and elevated fade zones
- Support/resistance context: 20-day lows/highs and 50-day/200-day moving averages
- Suggested option side, strike, and expiration
- Recent daily candlestick chart, covering the last 60 trading days, directly under each ranked setup
- Shaded origin zone showing support for CALL rebounds or resistance for PUT fades
- Estimated hold window for the setup to start working or be reassessed
- Entry plan explaining when to consider placing the trade next session
- Catalyst score from recent headlines, hype/social attention terms, and geopolitical or macro risk terms

It also keeps longer-term context:

- Momentum: 3-month, 6-month, and 1-year price trends plus 50-day/200-day moving averages
- Valuation: forward P/E when fundamentals are available, otherwise trailing P/E
- Risk: annualized volatility, max drawdown, and beta
- Income: dividend yield
- Recent Yahoo Finance headlines in the HTML report

The tool prints a terminal ranking and writes an HTML report.

This is an educational screening tool, not personalized financial advice. It can help narrow a research list, but it should not be the only basis for buying, selling, or holding an investment.

## Private Web App

Start the dashboard:

```bash
python3 stock_analyst.py --serve
```

Open:

```text
http://127.0.0.1:8765/app
```

The dashboard can:

- Run the full scanner and open `stock_report.html`
- Analyze one ticker on demand and open `on_demand_report.html`
- Link back to the latest full and on-demand reports

To use it from your phone on the same Wi-Fi:

```bash
python3 stock_analyst.py --serve --host 0.0.0.0
```

Then open `http://YOUR_MAC_IP:8765/app` on your phone.

For a private hosted version, set a password before starting the server:

```bash
STOCK_ANALYST_PASSWORD="choose-a-strong-password" python3 stock_analyst.py --serve --host 0.0.0.0
```

The login username is `stock`. Use HTTPS if this is exposed outside your home network.

## Cloud Phone Setup

Use this when you want the scanner available from your phone while your laptop is closed.

### Render deploy settings

This repo includes `render.yaml`, `Procfile`, and `requirements.txt`. On Render, create a new **Web Service** from the GitHub repo and use:

```text
Build command: pip install -r requirements.txt
Start command: python3 stock_analyst.py --serve --host 0.0.0.0
Health check path: /healthz
```

Add this environment variable in Render:

```text
STOCK_ANALYST_PASSWORD=choose-a-strong-password
```

Then open:

```text
https://YOUR-RENDER-APP.onrender.com/app
```

Login username:

```text
stock
```

### Phone workflow

1. Open the Render `/app` page from your phone.
2. Tap **Run full scanner**.
3. Open the full scanner report.
4. Expand the best setup.
5. Use the option side, strike, expiration, bid/ask, entry status, and entry plan as the trade ticket.
6. Place the order manually in Robinhood only if the trigger is active.

Important: the cloud app can scan and prepare the trade ticket, but it does not have the Codex Robinhood agentic tools. Real Robinhood execution still requires either manual placement in the Robinhood app or an explicit confirmed order through a Codex session that has Robinhood access.

## Quick Start

```bash
python3 stock_analyst.py
```

That screens the familiar high-liquidity stock universe for dip-rebound and spike-fade setups and writes `stock_report.html`. To scan the full common-stock market instead, add `--universe broad`.

For a faster test run:

```bash
python3 stock_analyst.py --max-symbols 200
```

Analyze specific tickers:

```bash
python3 stock_analyst.py AAPL MSFT NVDA GOOGL JPM
```

Use an optional smaller built-in list:

```bash
python3 stock_analyst.py --watchlist growth
python3 stock_analyst.py --watchlist income
python3 stock_analyst.py --watchlist defensive
```

Change the scoring profile:

```bash
python3 stock_analyst.py --profile growth
python3 stock_analyst.py --profile income
python3 stock_analyst.py --profile defensive
```

Write the report somewhere else:

```bash
python3 stock_analyst.py --output reports/today.html
```

Tune the screening rules:

```bash
python3 stock_analyst.py \
  --mode trade \
  --strategy reversal \
  --min-price 10 \
  --min-dollar-volume 50000000 \
  --min-setup-score 64 \
  --min-volume-ratio 0.8 \
  --min-reversal-move 0.03 \
  --limit 20
```

By default, the trade screen:

- Uses familiar, liquid individual stocks
- Excludes stocks under `$5`
- Excludes thinly traded stocks below `$50,000,000` average daily dollar volume
- Requires a reversal setup score of at least `64`
- Requires at least a `3%` 20-day dip for CALL candidates or `3%` 20-day spike for PUT candidates
- Checks recent headlines for catalyst, hype, and geopolitical/macro terms, then adjusts final rank
- Ranks both CALL and PUT setups
- Suggests a near-term option contract roughly 21-45 days out

For stricter A+ reversal hunting, use:

```bash
python3 stock_analyst.py \
  --mode trade \
  --strategy reversal \
  --direction both \
  --min-price 10 \
  --min-dollar-volume 100000000 \
  --min-setup-score 78 \
  --min-volume-ratio 1.0 \
  --min-reversal-move 0.05 \
  --limit 20 \
  --progress 25
```

Direction-only scans:

```bash
python3 stock_analyst.py --direction calls
python3 stock_analyst.py --direction puts
```

Use the older breakout continuation strategy:

```bash
python3 stock_analyst.py --strategy breakout
```

## Live Options Data

The script now uses Nasdaq's public website options-chain data by default:

```bash
python3 stock_analyst.py --options-provider nasdaq
```

This does not require a token or paid account. It is less stable than a dedicated market-data API because it depends on a public website endpoint.

Optional provider choices:

```bash
python3 stock_analyst.py --options-provider nasdaq
python3 stock_analyst.py --options-provider tradier
python3 stock_analyst.py --options-provider none
```

Tradier is still supported if you later want a more reliable authenticated provider:

```bash
export TRADIER_TOKEN="paste_your_token_here"
python3 stock_analyst.py --options-provider tradier
```

If the selected provider is blocked or unavailable, the script still estimates a contract structure using the setup direction, a slightly out-of-the-money strike, and the next suitable Friday expiration. Estimated contracts are marked `est.` and will not include live bid/ask/volume.

To skip options lookup entirely:

```bash
python3 stock_analyst.py --no-options
```

During a broad scan, the terminal prints progress with elapsed time and an estimated wait time:

```text
Screened 300/5000 symbols; 18 candidates kept; elapsed 4m 12s; ETA 1h 5m
```

Skip headline lookup:

```bash
python3 stock_analyst.py --no-news
```

Turn off catalyst-based ranking:

```bash
python3 stock_analyst.py --no-catalysts
```

Change how much catalysts affect the final rank:

```bash
python3 stock_analyst.py --catalyst-weight 0.40
```

The default catalyst weight is `0.30`, meaning the final trade rank is roughly `70%` chart setup and `30%` catalyst/news context.

Try fundamentals lookup:

```bash
python3 stock_analyst.py --fundamentals
```

Yahoo often blocks its quote/fundamentals endpoint, so fundamentals are off by default for now. Price history and headlines still run from live requests.

## Interpreting Results

- `Strong candidate`: high score under the selected profile
- `Candidate`: worth further research
- `Watchlist`: mixed signals
- `Avoid / wait`: weak score or risk concerns

Scores are relative screen outputs, not price targets or buy/sell recommendations. Before investing, review the company, valuation, earnings quality, balance sheet, competition, taxes, account type, time horizon, and your risk tolerance.

Trade entries are trigger-based. A setup in the report does not mean buy automatically at the next open; use the report's `Entry Plan` field for the condition to watch.

For short-term trades, the main criteria are:

- Liquidity: familiar individual stocks with high dollar volume; no index funds or ETFs in the default universe
- Chart quality: reversal setup score from pullback/spike size, RSI, support/resistance, moving averages, reversal-day behavior, and volume
- Direction: CALL for dip-rebound setups, PUT for spike-fade setups
- Catalyst alignment: headline keywords that support or conflict with the chart direction
- Geopolitical/macro impact: terms such as tariffs, sanctions, China/Taiwan, oil/OPEC, Middle East, export controls, war/conflict, and shipping stress
- Timing: entry plan is next-session trigger-based, with a hold estimate shown on each setup

## Data

The script fetches daily price data and recent headlines from Yahoo Finance endpoints at run time. This is live in the sense that it requests fresh data each time you run it, but it is not guaranteed tick-by-tick real-time market data. Market data can be delayed, missing, changed by the provider, or temporarily unavailable. Catalyst scoring is a transparent headline-keyword heuristic, not a full news desk or institutional NLP model, so verify major headlines before placing a trade.
