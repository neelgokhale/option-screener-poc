# Option Screener POC

AI-powered short-put option screener for the wheel strategy. Scans S&P 500 stocks daily, filters by fundamentals, risk, and sentiment, then ranks put contracts by expected value.

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- AlphaVantage API key (premium subscription recommended for 75 req/min)

### Install

```bash
uv sync
```

### Configure

Copy `.env.example` to `.env` and fill in your AlphaVantage key:

```bash
cp .env.example .env
```

Required:
- `ALPHAVANTAGE_API_KEY` — all market data, options chains, and news sentiment

Optional:
- `RESEND_API_KEY` / `ALERT_EMAIL_TO` — email alerts
- `S3_BUCKET_NAME` / AWS credentials — database backups

### Run

```bash
# Development server
uvicorn app.server:app --reload

# Frontend (separate terminal)
cd frontend && npm run dev

# Manual cron run
python cron.py
```

### Test

```bash
pytest
```

## Architecture

All market data flows through a single `AVClient` (rate-limited, cached, retried) with three thin adapters implementing the provider ABCs:

- `AVMarketDataAdapter` — stock profiles, price history, S&P 500 list
- `AVOptionsAdapter` — expiry dates, options chains
- `AVNewsAdapter` — sentiment analysis via NEWS_SENTIMENT

The backtest harness replays the screener on historical dates by threading an `as_of` date through every provider method.
