#!/usr/bin/env python3
"""
Stock Market Analyst

Ranks individual stocks from a watchlist using market data, recent headlines,
and transparent scoring. This is an educational screening tool, not personalized
financial advice.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html
import http.server
import json
import math
import os
import re
import subprocess
import statistics
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


WATCHLISTS = {
    "core": [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "AVGO",
        "COST",
        "LLY",
        "JPM",
        "V",
        "MA",
        "UNH",
    ],
    "growth": ["NVDA", "MSFT", "AMZN", "META", "AVGO", "AMD", "CRWD", "SNOW", "SHOP", "TSLA", "ADBE", "NOW"],
    "income": ["O", "VZ", "KO", "PEP", "JNJ", "PG", "XOM", "CVX", "JPM", "T", "PM", "MO"],
    "defensive": ["COST", "WMT", "PG", "KO", "PEP", "JNJ", "MRK", "MCD", "CL", "KMB", "GIS", "KR"],
    "personal": ["MSFT", "GOOGL", "ASTS", "ORCL", "AVGO", "NOW", "META", "NFLX", "RDW", "IONQ", "RIVN", "NKE"],
}
WATCHLIST_PATTERN_OVERRIDES = {
    "GOOGL": "Inverse head-and-shoulders",
}

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
TRADIER_BASE_URL = "https://api.tradier.com/v1"
NASDAQ_OPTIONS_URL = "https://api.nasdaq.com/api/quote/{symbol}/option-chain"
MACRO_NEWS_SYMBOLS = ("^GSPC", "^IXIC", "^VIX", "^TNX", "DX-Y.NYB", "CL=F", "GC=F", "SMH")
MARKET_CONTEXT_QUERIES = (
    "Federal Reserve rates inflation stock market",
    "Treasury yields dollar stocks market",
    "oil crude OPEC Middle East shipping stocks",
    "Strait of Hormuz Iran oil shipping market stocks",
    "Iran Strait of Hormuz crude oil shipping insurance",
    "China Taiwan export controls semiconductors stocks",
    "tariffs trade policy supply chain stocks",
    "VIX volatility risk appetite stocks",
    "earnings guidance mega cap technology stocks",
)
BAD_NAME_PARTS = (
    " ETF",
    " ETN",
    " FUND",
    " TRUST",
    " WARRANT",
    " RIGHT",
    " UNIT",
    " PREFERRED",
    " PFD",
    " DEPOSITARY",
    " NOTES",
    " NOTE",
    " BOND",
    " DEBENTURE",
    " ACQUISITION",
)
BAD_SYMBOL_PARTS = ("+", "^", "/", ".W", ".U", ".R", "-W", "-U", "-R")
POSITIVE_CATALYST_KEYWORDS = (
    "upgrade",
    "raises target",
    "price target raised",
    "beats",
    "beat estimates",
    "better-than-expected",
    "guidance raised",
    "raises guidance",
    "contract",
    "approval",
    "partnership",
    "launch",
    "buyback",
    "record revenue",
    "strong demand",
    "wins",
    "deal",
    "rally",
    "surge",
    "ai",
    "data center",
    "cloud",
    "chip",
)
NEGATIVE_CATALYST_KEYWORDS = (
    "downgrade",
    "cuts target",
    "price target cut",
    "misses",
    "missed estimates",
    "guidance cut",
    "cuts guidance",
    "probe",
    "lawsuit",
    "investigation",
    "recall",
    "ban",
    "antitrust",
    "fraud",
    "bankruptcy",
    "layoff",
    "slump",
    "falls",
    "plunges",
    "weak demand",
)
HYPE_KEYWORDS = (
    "meme",
    "reddit",
    "short squeeze",
    "squeeze",
    "viral",
    "retail traders",
    "social media",
    "wallstreetbets",
)
GEOPOLITICAL_KEYWORDS = (
    "china",
    "taiwan",
    "russia",
    "ukraine",
    "israel",
    "iran",
    "tariff",
    "tariffs",
    "sanction",
    "sanctions",
    "export control",
    "export controls",
    "opec",
    "oil",
    "middle east",
    "shipping",
    "red sea",
    "conflict",
    "war",
    "attack",
    "escalation",
)
OIL_SHOCK_KEYWORDS = (
    "strait of hormuz",
    "hormuz",
    "iran",
    "oil",
    "crude",
    "shipping",
    "tanker",
    "blockade",
    "closed",
    "closure",
    "shut",
    "shuts",
    "mines",
    "rerouting",
)
OIL_SHOCK_ACTION_KEYWORDS = (
    "closed",
    "closure",
    "shut",
    "shuts",
    "blocked",
    "blockade",
    "not allowed",
    "rerouting",
    "mines",
    "war risk",
    "surges",
    "jumps",
    "rises",
)
DEAL_CONTRACT_KEYWORDS = (
    "contract",
    "deal",
    "partnership",
    "order",
    "wins",
    "award",
    "supplier",
    "fleet",
    "agreement",
)
EARNINGS_GUIDANCE_KEYWORDS = (
    "earnings",
    "revenue",
    "profit",
    "margin",
    "guidance",
    "forecast",
    "estimates",
    "sales",
)
REGULATORY_LEGAL_KEYWORDS = (
    "lawsuit",
    "probe",
    "investigation",
    "regulatory",
    "antitrust",
    "approval",
    "fda",
    "sec",
    "recall",
    "ban",
)
PRODUCT_TECH_KEYWORDS = (
    "launch",
    "product",
    "ai",
    "artificial intelligence",
    "data center",
    "chip",
    "cloud",
    "semiconductor",
    "ev",
)
LOW_VALUE_NEWS_PHRASES = (
    "401(k)",
    "stocks to buy",
    "stock to buy",
    "good stock to buy",
    "best stock",
    "is it too late",
    "billionaire",
    "hedge fund",
    "likes",
    "price target",
    "analyst",
    "prediction",
    "rank",
    "zacks",
    "motley fool",
    "in focus",
    "midday stories",
    "sector update",
    "stock price, quote, news",
    "stock price quote",
    "earnings call transcript",
    "check out",
    "real time",
    "summer reading list",
    "dow end",
    "s&p 500",
    "nasdaq",
)
MAJOR_NEWS_KEYWORDS = (
    DEAL_CONTRACT_KEYWORDS
    + EARNINGS_GUIDANCE_KEYWORDS
    + REGULATORY_LEGAL_KEYWORDS
    + PRODUCT_TECH_KEYWORDS
    + GEOPOLITICAL_KEYWORDS
    + HYPE_KEYWORDS
    + ("merger", "acquisition", "ipo", "spinoff", "bankruptcy", "layoff", "strike", "outage")
)
PREFERRED_NEWS_SOURCES = (
    "Bloomberg",
    "Reuters",
    "CNBC",
    "Seeking Alpha",
    "MarketWatch",
    "Barron's",
    "Benzinga",
    "Investor's Business Daily",
    "Wall Street Journal",
)
PREFERRED_NEWS_SOURCE_QUERY = (
    "site:bloomberg.com OR site:reuters.com OR site:cnbc.com OR site:seekingalpha.com "
    "OR site:marketwatch.com OR site:barrons.com OR site:wsj.com OR site:benzinga.com OR site:investors.com"
)
SECTOR_MACRO_TERMS = {
    "energy": (
        "oil", "crude", "opec", "energy", "gasoline", "refinery", "lng", "natural gas",
        "iran", "middle east", "red sea", "shipping", "sanction", "war", "conflict",
    ),
    "semis": (
        "ai", "chip", "chips", "semiconductor", "data center", "export control",
        "china", "taiwan", "cloud", "gpu", "memory",
    ),
    "software": ("ai", "cloud", "data center", "cyber", "enterprise", "software", "antitrust"),
    "financials": ("fed", "rates", "yield", "credit", "loan", "ipo", "bank", "banking", "dealmaking", "inflation"),
    "consumer": ("consumer", "retail", "inflation", "tariff", "spending", "restaurant", "travel", "discretionary"),
    "industrial": ("aerospace", "defense", "aircraft", "contract", "shipping", "freight", "tariff", "war", "supply chain"),
    "healthcare": ("fda", "drug", "medicare", "healthcare", "trial", "approval", "withdrawal", "patent"),
}
SYMBOL_SECTORS = {
    "XOM": "energy", "CVX": "energy", "OXY": "energy", "SLB": "energy", "COP": "energy", "VLO": "energy", "MPC": "energy", "HAL": "energy",
    "NVDA": "semis", "AMD": "semis", "ARM": "semis", "AVGO": "semis", "MU": "semis", "INTC": "semis", "QCOM": "semis", "SMCI": "semis",
    "MSFT": "software", "META": "software", "GOOGL": "software", "ORCL": "software", "CRM": "software", "ADBE": "software", "NOW": "software", "SNOW": "software", "CRWD": "software", "PANW": "software", "NET": "software", "PLTR": "software",
    "JPM": "financials", "BAC": "financials", "WFC": "financials", "GS": "financials", "MS": "financials", "C": "financials", "AXP": "financials", "PYPL": "financials", "V": "financials", "MA": "financials",
    "WMT": "consumer", "COST": "consumer", "HD": "consumer", "LOW": "consumer", "TGT": "consumer", "NKE": "consumer", "SBUX": "consumer", "MCD": "consumer", "DIS": "consumer", "CMG": "consumer", "AMZN": "consumer", "TSLA": "consumer", "UBER": "consumer", "ABNB": "consumer", "DASH": "consumer", "NFLX": "consumer",
    "BA": "industrial", "CAT": "industrial", "DE": "industrial", "GE": "industrial", "LMT": "industrial", "RTX": "industrial", "HON": "industrial", "UPS": "industrial", "FDX": "industrial",
    "LLY": "healthcare", "UNH": "healthcare", "MRNA": "healthcare", "PFE": "healthcare", "JNJ": "healthcare", "ABBV": "healthcare", "TMO": "healthcare", "ISRG": "healthcare", "VRTX": "healthcare", "AMGN": "healthcare",
}
SECTOR_BENCHMARKS = {
    "energy": "XLE",
    "semis": "SMH",
    "software": "IGV",
    "financials": "XLF",
    "consumer": "XLY",
    "industrial": "XLI",
    "healthcare": "XLV",
}
SYMBOL_ALIASES = {
    "AAPL": ("apple",),
    "MSFT": ("microsoft",),
    "NVDA": ("nvidia",),
    "AMZN": ("amazon", "aws"),
    "GOOGL": ("google", "alphabet"),
    "META": ("meta", "facebook", "instagram"),
    "TSLA": ("tesla",),
    "AMD": ("amd", "advanced micro devices"),
    "XOM": ("exxon", "exxonmobil"),
    "HAL": ("halliburton",),
    "ORCL": ("oracle",),
    "GS": ("goldman", "goldman sachs"),
    "JPM": ("jpmorgan", "jp morgan", "chase"),
    "BAC": ("bank of america", "bofa"),
    "C": ("citigroup", "citi"),
    "GE": ("general electric", "ge aerospace"),
    "PLTR": ("palantir",),
    "DIS": ("disney",),
    "UBER": ("uber",),
    "AMGN": ("amgen",),
    "TGT": ("target",),
    "COST": ("costco",),
    "HD": ("home depot",),
    "LOW": ("lowe's", "lowes"),
    "DE": ("deere", "john deere"),
    "DASH": ("doordash", "door dash"),
    "ABNB": ("airbnb",),
    "WFC": ("wells fargo",),
    "AXP": ("american express",),
    "V": ("visa",),
    "MA": ("mastercard",),
    "NOW": ("servicenow", "service now"),
    "NET": ("cloudflare",),
    "CAT": ("caterpillar",),
    "GE": ("ge aerospace", "general electric"),
    "ARM": ("arm ", "arm holdings"),
    "JNJ": ("johnson & johnson",),
}
AMBIGUOUS_SYMBOL_TERMS = {
    "ARM", "C", "CAT", "COST", "DASH", "DE", "GE", "HD", "LOW", "MA", "NET", "NOW", "T", "V"
}
LIQUID_OPTIONS_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "NFLX", "AVGO",
    "SMCI", "PLTR", "COIN", "MSTR", "ARM", "MU", "INTC", "QCOM", "CRM", "ORCL",
    "ADBE", "NOW", "SHOP", "UBER", "ABNB", "DASH", "SNOW", "CRWD", "PANW", "NET",
    "JPM", "BAC", "WFC", "GS", "MS", "C", "V", "MA", "AXP", "PYPL",
    "LLY", "UNH", "MRNA", "PFE", "JNJ", "ABBV", "TMO", "ISRG", "VRTX", "AMGN",
    "XOM", "CVX", "OXY", "SLB", "COP", "VLO", "MPC", "HAL",
    "WMT", "COST", "HD", "LOW", "TGT", "NKE", "SBUX", "MCD", "DIS", "CMG",
    "BA", "CAT", "DE", "GE", "LMT", "RTX", "HON", "UPS", "FDX",
]
COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms, Inc.",
    "TSLA": "Tesla, Inc.",
    "AMD": "Advanced Micro Devices, Inc.",
    "NFLX": "Netflix, Inc.",
    "AVGO": "Broadcom Inc.",
    "SMCI": "Super Micro Computer, Inc.",
    "PLTR": "Palantir Technologies Inc.",
    "COIN": "Coinbase Global, Inc.",
    "MSTR": "MicroStrategy Incorporated",
    "ARM": "Arm Holdings plc",
    "MU": "Micron Technology, Inc.",
    "INTC": "Intel Corporation",
    "QCOM": "QUALCOMM Incorporated",
    "CRM": "Salesforce, Inc.",
    "ORCL": "Oracle Corporation",
    "ADBE": "Adobe Inc.",
    "NOW": "ServiceNow, Inc.",
    "SHOP": "Shopify Inc.",
    "UBER": "Uber Technologies, Inc.",
    "ABNB": "Airbnb, Inc.",
    "DASH": "DoorDash, Inc.",
    "SNOW": "Snowflake Inc.",
    "CRWD": "CrowdStrike Holdings, Inc.",
    "PANW": "Palo Alto Networks, Inc.",
    "NET": "Cloudflare, Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "BAC": "Bank of America Corporation",
    "WFC": "Wells Fargo & Company",
    "GS": "The Goldman Sachs Group, Inc.",
    "MS": "Morgan Stanley",
    "C": "Citigroup Inc.",
    "V": "Visa Inc.",
    "MA": "Mastercard Incorporated",
    "AXP": "American Express Company",
    "PYPL": "PayPal Holdings, Inc.",
    "LLY": "Eli Lilly and Company",
    "UNH": "UnitedHealth Group Incorporated",
    "MRNA": "Moderna, Inc.",
    "PFE": "Pfizer Inc.",
    "JNJ": "Johnson & Johnson",
    "ABBV": "AbbVie Inc.",
    "TMO": "Thermo Fisher Scientific Inc.",
    "ISRG": "Intuitive Surgical, Inc.",
    "VRTX": "Vertex Pharmaceuticals Incorporated",
    "AMGN": "Amgen Inc.",
    "XOM": "Exxon Mobil Corporation",
    "CVX": "Chevron Corporation",
    "OXY": "Occidental Petroleum Corporation",
    "SLB": "Schlumberger Limited",
    "COP": "ConocoPhillips",
    "VLO": "Valero Energy Corporation",
    "MPC": "Marathon Petroleum Corporation",
    "HAL": "Halliburton Company",
    "WMT": "Walmart Inc.",
    "COST": "Costco Wholesale Corporation",
    "HD": "The Home Depot, Inc.",
    "LOW": "Lowe's Companies, Inc.",
    "TGT": "Target Corporation",
    "NKE": "NIKE, Inc.",
    "SBUX": "Starbucks Corporation",
    "MCD": "McDonald's Corporation",
    "DIS": "The Walt Disney Company",
    "CMG": "Chipotle Mexican Grill, Inc.",
    "BA": "The Boeing Company",
    "CAT": "Caterpillar Inc.",
    "DE": "Deere & Company",
    "GE": "GE Aerospace",
    "LMT": "Lockheed Martin Corporation",
    "RTX": "RTX Corporation",
    "HON": "Honeywell International Inc.",
    "UPS": "United Parcel Service, Inc.",
    "FDX": "FedEx Corporation",
}


@dataclass
class PriceSeries:
    symbol: str
    dates: list[dt.date]
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[int]


@dataclass
class Quote:
    symbol: str
    name: str = ""
    exchange: str = ""
    sector: str = ""
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    analyst_rating: str = ""


@dataclass
class NewsItem:
    title: str
    link: str
    published: str
    source: str = ""


@dataclass
class CatalystAssessment:
    score: float
    label: str
    notes: list[str]


@dataclass
class OptionContract:
    contract_symbol: str
    side: str
    strike: float
    expiration: dt.date
    bid: float | None
    ask: float | None
    last_price: float | None
    volume: int | None
    open_interest: int | None
    implied_volatility: float | None
    estimated: bool = False


@dataclass
class PatternDetection:
    pattern_type: str
    direction: str
    start_index: int
    end_index: int
    upper_start: tuple[int, float]
    upper_end: tuple[int, float]
    lower_start: tuple[int, float]
    lower_end: tuple[int, float]
    upper_slope: float
    lower_slope: float
    convergence_score: float
    breakout_index: int | None
    breakout_volume_ratio: float | None
    confidence: float
    mode: str = "strict"
    pivot_highs: list[tuple[int, float]] | None = None
    pivot_lows: list[tuple[int, float]] | None = None
    validation_notes: list[str] | None = None


@dataclass
class OptionsOpportunityScore:
    ticker: str
    call_score: float
    put_score: float
    confidence: float
    bullish_factors: list[str]
    bearish_factors: list[str]
    missing_data: list[str]
    risk_factors: list[str]
    invalidation_conditions: list[str]
    summary: str


@dataclass
class NormalizedEvent:
    event_id: str
    ticker: str
    source: str
    headline: str
    event_type: str
    direction: str
    confidence: float
    novelty_score: float
    urgency_score: float
    timestamp: str
    transmission_path: list[str]
    summary: str


@dataclass
class OpportunityRejection:
    action: str
    reasons: list[str]
    expected_move_pct: float | None
    implied_move_pct: float | None
    estimated_edge_pct: float | None


@dataclass
class UniverseStock:
    symbol: str
    name: str
    exchange: str


@dataclass
class Analysis:
    symbol: str
    name: str
    price: float
    score: float
    rating: str
    momentum_score: float
    value_score: float
    risk_score: float
    yield_score: float
    return_1y: float | None
    return_6m: float | None
    return_3m: float | None
    volatility: float | None
    max_drawdown: float | None
    sharpe_like: float | None
    rsi: float | None
    sma_50: float | None
    sma_200: float | None
    market_cap: float | None
    pe: float | None
    dividend_yield: float | None
    beta: float | None
    notes: list[str]
    news: list[NewsItem]
    average_dollar_volume: float | None = None
    setup_score: float | None = None
    setup_label: str = ""
    setup_notes: list[str] | None = None
    return_1d: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    volume_ratio: float | None = None
    setup_direction: str = ""
    setup_strategy: str = ""
    option: OptionContract | None = None
    chart_dates: list[str] | None = None
    chart_opens: list[float] | None = None
    chart_highs: list[float] | None = None
    chart_lows: list[float] | None = None
    chart_closes: list[float] | None = None
    four_hour_dates: list[str] | None = None
    four_hour_opens: list[float] | None = None
    four_hour_highs: list[float] | None = None
    four_hour_lows: list[float] | None = None
    four_hour_closes: list[float] | None = None
    four_hour_volumes: list[int] | None = None
    intraday_dates: list[str] | None = None
    intraday_opens: list[float] | None = None
    intraday_highs: list[float] | None = None
    intraday_lows: list[float] | None = None
    intraday_closes: list[float] | None = None
    intraday_volumes: list[int] | None = None
    hold_estimate: str = ""
    entry_plan: str = ""
    catalyst_score: float | None = None
    catalyst_label: str = ""
    catalyst_notes: list[str] | None = None
    final_trade_score: float | None = None
    macro_news: list[NewsItem] | None = None
    trade_brief: "TradeBrief | None" = None
    pattern_detection: PatternDetection | None = None
    options_opportunity: OptionsOpportunityScore | None = None
    normalized_events: list[NormalizedEvent] | None = None
    opportunity_rejection: OpportunityRejection | None = None


@dataclass
class TradeBrief:
    thesis: str
    pattern: str
    pattern_status: str
    confirmation_level: float | None
    measured_move: float | None
    invalidation: float | None
    stop_loss: float | None
    target_1: float | None
    target_2: float | None
    target_3: float | None
    risk_reward: float | None
    market_structure: str
    timeframe_supporting: list[str]
    timeframe_opposing: list[str]
    alignment_score: float
    indicator_analysis: str
    volume_analysis: str
    relative_strength: str
    support_resistance: str
    volume_profile: str
    liquidity_analysis: str
    options_flow: str
    order_flow: str
    catalyst_analysis: str
    market_environment: str
    event_risk: str
    bull_case: str
    base_case: str
    bear_case: str
    confidence_score: float
    setup_grade: str
    take_reasons: list[str]
    avoid_reasons: list[str]
    final_recommendation: str


@dataclass
class TradeDecision:
    tier: str
    status: str
    stance: str
    notify: bool
    trader_score: float
    contract_score: float
    catalyst_score: float
    reasons: list[str]
    blockers: list[str]


def fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 stock-analyst/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_tradier_json(path: str, params: dict[str, str] | None = None, timeout: int = 20) -> dict[str, Any]:
    token = os.environ.get("TRADIER_TOKEN")
    if not token:
        raise ValueError("TRADIER_TOKEN is not set")
    query = urllib.parse.urlencode(params or {})
    url = f"{TRADIER_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "stock-analyst/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_nasdaq_json(symbol: str, timeout: int = 5) -> dict[str, Any]:
    encoded = urllib.parse.quote(symbol.upper())
    url = NASDAQ_OPTIONS_URL.format(symbol=encoded) + "?assetclass=stocks&limit=9999"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 stock-analyst/1.0",
            "Accept": "application/json,text/plain,*/*",
            "Origin": "https://www.nasdaq.com",
            "Referer": f"https://www.nasdaq.com/market-activity/stocks/{encoded.lower()}/option-chain",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 stock-analyst/1.0",
            "Accept": "application/rss+xml,application/xml,text/xml,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_price_series(symbol: str, days: int = 420) -> PriceSeries:
    now = int(time.time())
    start = now - days * 24 * 60 * 60
    encoded = urllib.parse.quote(symbol.upper())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={start}&period2={now}&interval=1d&events=history"
    )
    payload = fetch_json(url)
    result = payload.get("chart", {}).get("result") or []
    if not result:
        error = payload.get("chart", {}).get("error") or {}
        raise ValueError(error.get("description") or f"No price data for {symbol}")

    item = result[0]
    timestamps = item.get("timestamp") or []
    quote = (item.get("indicators", {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    dates: list[dt.date] = []
    clean_opens: list[float] = []
    clean_highs: list[float] = []
    clean_lows: list[float] = []
    clean_closes: list[float] = []
    clean_volumes: list[int] = []
    for timestamp, open_price, high, low, close, volume in zip(timestamps, opens, highs, lows, closes, volumes):
        if open_price is None or high is None or low is None or close is None:
            continue
        dates.append(dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc).date())
        clean_opens.append(float(open_price))
        clean_highs.append(float(high))
        clean_lows.append(float(low))
        clean_closes.append(float(close))
        clean_volumes.append(int(volume or 0))

    if len(clean_closes) < 60:
        raise ValueError(f"Only {len(clean_closes)} usable price points for {symbol}")
    return PriceSeries(
        symbol=symbol.upper(),
        dates=dates,
        opens=clean_opens,
        highs=clean_highs,
        lows=clean_lows,
        closes=clean_closes,
        volumes=clean_volumes,
    )


def fetch_intraday_series(symbol: str, interval: str = "15m", days: int = 5, limit: int = 80) -> tuple[list[str], list[float], list[float], list[float], list[float]]:
    labels, opens, highs, lows, closes, _volumes = fetch_intraday_ohlcv(symbol, interval, days, limit)
    return labels, opens, highs, lows, closes


def fetch_intraday_ohlcv(symbol: str, interval: str = "15m", days: int = 5, limit: int = 80) -> tuple[list[str], list[float], list[float], list[float], list[float], list[int]]:
    now = int(time.time())
    start = now - days * 24 * 60 * 60
    encoded = urllib.parse.quote(symbol.upper())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={start}&period2={now}&interval={urllib.parse.quote(interval)}"
    )
    payload = fetch_json(url)
    result = payload.get("chart", {}).get("result") or []
    if not result:
        error = payload.get("chart", {}).get("error") or {}
        raise ValueError(error.get("description") or f"No intraday data for {symbol}")

    item = result[0]
    timestamps = item.get("timestamp") or []
    quote = (item.get("indicators", {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    labels: list[str] = []
    clean_opens: list[float] = []
    clean_highs: list[float] = []
    clean_lows: list[float] = []
    clean_closes: list[float] = []
    clean_volumes: list[int] = []
    for timestamp, open_price, high, low, close, volume in zip(timestamps, opens, highs, lows, closes, volumes):
        if open_price is None or high is None or low is None or close is None:
            continue
        stamp = dt.datetime.fromtimestamp(timestamp).astimezone()
        labels.append(stamp.strftime("%m-%d %H:%M"))
        clean_opens.append(float(open_price))
        clean_highs.append(float(high))
        clean_lows.append(float(low))
        clean_closes.append(float(close))
        clean_volumes.append(int(volume or 0))

    if len(clean_closes) < 10:
        raise ValueError(f"Only {len(clean_closes)} usable intraday points for {symbol}")
    return labels[-limit:], clean_opens[-limit:], clean_highs[-limit:], clean_lows[-limit:], clean_closes[-limit:], clean_volumes[-limit:]


def aggregate_bars(
    labels: list[str],
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
    group_size: int,
) -> tuple[list[str], list[float], list[float], list[float], list[float], list[int]]:
    grouped_labels: list[str] = []
    grouped_opens: list[float] = []
    grouped_highs: list[float] = []
    grouped_lows: list[float] = []
    grouped_closes: list[float] = []
    grouped_volumes: list[int] = []
    usable = min(len(labels), len(opens), len(highs), len(lows), len(closes), len(volumes))
    for start in range(0, usable, group_size):
        end = min(start + group_size, usable)
        if end - start < max(2, group_size // 2):
            continue
        grouped_labels.append(labels[start])
        grouped_opens.append(opens[start])
        grouped_highs.append(max(highs[start:end]))
        grouped_lows.append(min(lows[start:end]))
        grouped_closes.append(closes[end - 1])
        grouped_volumes.append(sum(volumes[start:end]))
    return grouped_labels[-80:], grouped_opens[-80:], grouped_highs[-80:], grouped_lows[-80:], grouped_closes[-80:], grouped_volumes[-80:]


def fetch_four_hour_series(symbol: str, days: int = 75) -> tuple[list[str], list[float], list[float], list[float], list[float]]:
    labels, opens, highs, lows, closes, _volumes = fetch_four_hour_ohlcv(symbol, days)
    return labels, opens, highs, lows, closes


def fetch_four_hour_ohlcv(symbol: str, days: int = 75) -> tuple[list[str], list[float], list[float], list[float], list[float], list[int]]:
    labels, opens, highs, lows, closes, volumes = fetch_intraday_ohlcv(symbol, interval="60m", days=days, limit=320)
    return aggregate_bars(labels, opens, highs, lows, closes, volumes, 4)


def fetch_quotes(symbols: Iterable[str]) -> dict[str, Quote]:
    symbols = [symbol.upper() for symbol in symbols]
    if not symbols:
        return {}

    quotes: dict[str, Quote] = {}
    for chunk in chunks(symbols, 40):
        encoded = urllib.parse.quote(",".join(chunk))
        fields = ",".join(
            [
                "symbol",
                "shortName",
                "longName",
                "fullExchangeName",
                "sector",
                "marketCap",
                "trailingPE",
                "forwardPE",
                "dividendYield",
                "beta",
                "averageAnalystRating",
            ]
        )
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={encoded}&fields={fields}"
        payload = fetch_json(url)
        for raw in payload.get("quoteResponse", {}).get("result", []):
            symbol = str(raw.get("symbol", "")).upper()
            quotes[symbol] = Quote(
                symbol=symbol,
                name=str(raw.get("longName") or raw.get("shortName") or symbol),
                exchange=str(raw.get("fullExchangeName") or ""),
                sector=str(raw.get("sector") or ""),
                market_cap=as_float(raw.get("marketCap")),
                trailing_pe=as_float(raw.get("trailingPE")),
                forward_pe=as_float(raw.get("forwardPE")),
                dividend_yield=normal_yield(raw.get("dividendYield")),
                beta=as_float(raw.get("beta")),
                analyst_rating=str(raw.get("averageAnalystRating") or ""),
            )
        time.sleep(0.1)
    return quotes


def fetch_market_universe() -> list[UniverseStock]:
    universe = fetch_nasdaq_listed() + fetch_other_listed()
    seen: set[str] = set()
    stocks: list[UniverseStock] = []
    for item in universe:
        if item.symbol in seen:
            continue
        seen.add(item.symbol)
        stocks.append(item)
    return sorted(stocks, key=lambda item: item.symbol)


def nyse_nasdaq_universe(universe: list[UniverseStock]) -> list[UniverseStock]:
    return [item for item in universe if item.exchange in {"NASDAQ", "N"}]


def fetch_nasdaq_listed() -> list[UniverseStock]:
    rows = parse_pipe_table(fetch_text(NASDAQ_LISTED_URL))
    stocks: list[UniverseStock] = []
    for row in rows:
        symbol = normalize_symbol(row.get("Symbol", ""))
        name = row.get("Security Name", "").strip()
        if (
            row.get("Test Issue", "").strip().upper() == "Y"
            or row.get("ETF", "").strip().upper() == "Y"
            or not is_common_stock(symbol, name)
        ):
            continue
        stocks.append(UniverseStock(symbol=symbol, name=name, exchange="NASDAQ"))
    return stocks


def fetch_other_listed() -> list[UniverseStock]:
    rows = parse_pipe_table(fetch_text(OTHER_LISTED_URL))
    stocks: list[UniverseStock] = []
    for row in rows:
        symbol = normalize_symbol(row.get("ACT Symbol", ""))
        name = row.get("Security Name", "").strip()
        if (
            row.get("Test Issue", "").strip().upper() == "Y"
            or row.get("ETF", "").strip().upper() == "Y"
            or not is_common_stock(symbol, name)
        ):
            continue
        exchange = row.get("Exchange", "").strip() or "OTHER"
        stocks.append(UniverseStock(symbol=symbol, name=name, exchange=exchange))
    return stocks


def parse_pipe_table(raw: str) -> list[dict[str, str]]:
    lines = [line for line in raw.splitlines() if line and not line.startswith("File Creation Time:")]
    if not lines:
        return []
    headers = lines[0].split("|")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cells = line.split("|")
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace("$", "-")


def display_company_name(symbol: str, name: str = "") -> str:
    cleaned = name.strip()
    if cleaned and cleaned.upper() != symbol.upper():
        return cleaned
    return COMPANY_NAMES.get(symbol.upper(), cleaned or symbol.upper())


def is_common_stock(symbol: str, name: str) -> bool:
    if not symbol or any(part in symbol for part in BAD_SYMBOL_PARTS):
        return False
    upper_name = f" {name.upper()} "
    return not any(part in upper_name for part in BAD_NAME_PARTS)


def fetch_news(symbol: str, limit: int = 12) -> list[NewsItem]:
    encoded = urllib.parse.quote(symbol.upper())
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={encoded}&region=US&lang=en-US"
    raw = fetch_text(url, timeout=8)
    root = ET.fromstring(raw)
    items: list[NewsItem] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        source = detect_news_source(title, link)
        if title:
            items.append(NewsItem(title=title, link=link, published=published, source=source))
        if len(items) >= limit:
            break
    return items


def fetch_macro_news(limit_per_symbol: int = 5) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen: set[str] = set()
    for symbol in MACRO_NEWS_SYMBOLS:
        try:
            for item in fetch_news(symbol, limit_per_symbol):
                key = item.title.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    items.append(item)
        except Exception:
            continue
    for query in MARKET_CONTEXT_QUERIES:
        try:
            for item in fetch_google_news_search(query, limit=3):
                key = item.title.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    items.append(item)
        except Exception:
            continue
    return dedupe_news(items)


def fetch_preferred_source_news(symbol: str, name: str, limit: int = 6) -> list[NewsItem]:
    aliases = list(SYMBOL_ALIASES.get(symbol.upper(), ()))
    company_term = aliases[0] if aliases else first_company_name_token(name)
    query_parts = [symbol.upper(), "stock"]
    if company_term:
        query_parts.append(company_term)
    query_parts.append("(site:bloomberg.com OR site:seekingalpha.com OR site:cnbc.com)")
    query = " ".join(query_parts)
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    )
    raw = fetch_text(url)
    root = ET.fromstring(raw)
    items: list[NewsItem] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip() or detect_news_source(title, link)
        source = normalize_preferred_source(source, title, link)
        if title and source in PREFERRED_NEWS_SOURCES and is_relevant_preferred_headline(symbol, name, title):
            items.append(NewsItem(title=title, link=link, published=published, source=source))
        if len(items) >= limit:
            break
    return items


def fetch_google_news_search(query: str, limit: int = 10) -> list[NewsItem]:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    )
    raw = fetch_text(url, timeout=4)
    root = ET.fromstring(raw)
    items: list[NewsItem] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip() or detect_news_source(title, link)
        source = normalize_preferred_source(source, title, link)
        if title:
            items.append(NewsItem(title=title, link=link, published=published, source=source))
        if len(items) >= limit:
            break
    return items


def fetch_deep_research_news(symbol: str, name: str, limit: int = 16) -> list[NewsItem]:
    aliases = list(SYMBOL_ALIASES.get(symbol.upper(), ()))
    company_term = aliases[0] if aliases else first_company_name_token(name)
    identity = f"{symbol.upper()} stock"
    if company_term:
        identity = f"{symbol.upper()} {company_term} stock"
    query_topics = (
        "",
        "(earnings OR revenue OR guidance OR margin OR forecast)",
        "(deal OR contract OR partnership OR order OR acquisition OR AI OR cloud OR chip OR data center OR lawsuit OR regulation OR tariff OR China OR Iran OR Fed OR rates OR inflation OR geopolitical)",
    )
    items: list[NewsItem] = []
    for topic in query_topics:
        query = f"{identity} {topic} ({PREFERRED_NEWS_SOURCE_QUERY})".strip()
        try:
            items.extend(fetch_google_news_search(query, limit=6))
        except Exception:
            continue
        items = dedupe_news(items)
        if len(items) >= limit:
            break

    relevant = [
        news_item
        for news_item in dedupe_news(items)
        if is_relevant_preferred_headline(symbol, name, news_item.title)
        and not is_low_value_headline(news_item.title.lower())
    ]
    if len(relevant) < min(8, limit):
        relevant = dedupe_news(relevant + fetch_preferred_source_news(symbol, name, limit=limit))
    return relevant[:limit]


def first_company_name_token(name: str) -> str:
    for token in re.findall(r"[A-Za-z][A-Za-z&]+", name):
        lowered = token.lower()
        if len(token) >= 4 and lowered not in {"corp", "corporation", "company", "inc", "incorporated", "class"}:
            return token
    return ""


def is_relevant_preferred_headline(symbol: str, name: str, title: str) -> bool:
    cleaned = clean_headline(title)
    lowered = cleaned.lower()
    if lowered in {"bloomberg", "bloomberg europe", "bloomberg asia", "seeking alpha", "cnbc"}:
        return False
    if "business news, stock markets" in lowered:
        return False
    if any(contains_keyword(lowered, term) for term in relevance_terms(symbol, name)):
        return True
    return False


def detect_news_source(title: str, link: str) -> str:
    text = f"{title} {link}".lower()
    if "bloomberg" in text:
        return "Bloomberg"
    if "seekingalpha" in text or "seeking alpha" in text:
        return "Seeking Alpha"
    if "cnbc" in text:
        return "CNBC"
    parsed = urllib.parse.urlparse(link)
    domain = parsed.netloc.lower().removeprefix("www.")
    if domain:
        return domain.split(".")[0].replace("-", " ").title()
    return ""


def normalize_preferred_source(source: str, title: str = "", link: str = "") -> str:
    text = f"{source} {title} {link}".lower()
    if "bloomberg" in text:
        return "Bloomberg"
    if "seekingalpha" in text or "seeking alpha" in text:
        return "Seeking Alpha"
    if "cnbc" in text:
        return "CNBC"
    return source


def assess_catalysts(news: list[NewsItem], direction: str) -> CatalystAssessment:
    if not news:
        return CatalystAssessment(50.0, "No fresh catalyst", ["no recent headlines available"])

    scored_news = major_news_items(news) or non_low_value_news(news)
    if not scored_news:
        return CatalystAssessment(50.0, "No major catalyst", ["only low-value analyst/opinion headlines found"])

    positive_hits = keyword_hits(scored_news, POSITIVE_CATALYST_KEYWORDS)
    negative_hits = keyword_hits(scored_news, NEGATIVE_CATALYST_KEYWORDS)
    hype_hits = keyword_hits(scored_news, HYPE_KEYWORDS)
    geopolitical_hits = keyword_hits(scored_news, GEOPOLITICAL_KEYWORDS)

    positive = len(positive_hits)
    negative = len(negative_hits)
    hype = len(hype_hits)
    geopolitical = len(geopolitical_hits)

    score = 50.0
    notes: list[str] = []
    if direction == "CALL":
        score += positive * 14
        score -= negative * 16
        score -= geopolitical * 8
    elif direction == "PUT":
        score += negative * 14
        score += geopolitical * 9
        score -= positive * 12
    else:
        score += positive * 8
        score -= negative * 8
        score -= geopolitical * 4

    if hype:
        score += 4 if direction == "CALL" else 2
        notes.append("hype/social attention detected; treat position sizing carefully")
    if positive_hits:
        notes.append(f"bullish catalyst words: {', '.join(positive_hits[:4])}")
    if negative_hits:
        notes.append(f"bearish/risk words: {', '.join(negative_hits[:4])}")
    if geopolitical_hits:
        notes.append(f"geopolitical/macro words: {', '.join(geopolitical_hits[:4])}")

    score = clamp(score)
    if score >= 76:
        label = "Strong catalyst alignment"
    elif score >= 62:
        label = "Catalyst support"
    elif score <= 36:
        label = "Catalyst conflict"
    elif score <= 45:
        label = "Catalyst caution"
    else:
        label = "Neutral catalyst"
    return CatalystAssessment(round(score, 1), label, notes or ["headlines are present but no major catalyst keywords matched"])


def macro_oil_shock(news: list[NewsItem]) -> dict[str, float | bool | str]:
    if not news:
        return {"active": False, "score": 0.0, "label": "", "evidence": ""}
    best_score = 0.0
    best_title = ""
    for news_item in non_low_value_news(news):
        title = clean_headline(news_item.title)
        text = title.lower()
        has_hormuz = contains_keyword(text, "strait of hormuz") or contains_keyword(text, "hormuz")
        has_iran = contains_keyword(text, "iran")
        has_oil = contains_keyword(text, "oil") or contains_keyword(text, "crude")
        has_action = any(contains_keyword(text, keyword) for keyword in OIL_SHOCK_ACTION_KEYWORDS)
        has_shipping = any(contains_keyword(text, keyword) for keyword in ("shipping", "tanker", "rerouting", "insurance", "mines"))
        score = 0.0
        if has_hormuz and has_action:
            score = 100.0
        elif has_hormuz and (has_oil or has_shipping):
            score = 88.0
        elif has_iran and has_oil and has_action:
            score = 82.0
        elif has_iran and has_shipping:
            score = 74.0
        elif has_oil and has_action:
            score = 66.0
        if score > best_score:
            best_score = score
            best_title = title
    active = best_score >= 70
    if best_score >= 90:
        label = "Strait/Hormuz oil shock"
    elif active:
        label = "Iran/oil risk-off shock"
    else:
        label = ""
    return {"active": active, "score": best_score, "label": label, "evidence": best_title}


def macro_adjusted_catalyst_score(item: Analysis, assessment: CatalystAssessment, macro_shock: dict[str, float | bool | str] | None) -> CatalystAssessment:
    if not macro_shock or not macro_shock.get("active"):
        return assessment
    direction = item.setup_direction or "CALL"
    sector = SYMBOL_SECTORS.get(item.symbol.upper(), "")
    shock_label = str(macro_shock.get("label") or "oil/geopolitical shock")
    evidence = str(macro_shock.get("evidence") or "").strip()
    score = assessment.score
    notes = list(assessment.notes)
    if evidence:
        notes.append(f"macro shock: {evidence}")
    if direction == "CALL":
        if sector == "energy":
            score += 12
            notes.append(f"{shock_label} can support energy calls, but entry still needs tape confirmation")
        else:
            score -= 20
            notes.append(f"{shock_label} is risk-off for normal calls; broad call setups require extra confirmation")
    elif direction == "PUT":
        if sector == "energy":
            score -= 10
            notes.append(f"{shock_label} works against energy puts unless crude reverses")
        else:
            score += 12
            notes.append(f"{shock_label} supports defensive put bias in non-energy names")
    score = clamp(score)
    if score >= 76:
        label = "Strong catalyst alignment"
    elif score >= 62:
        label = "Catalyst support"
    elif score <= 36:
        label = "Catalyst conflict"
    elif score <= 45:
        label = "Catalyst caution"
    else:
        label = "Neutral catalyst"
    return CatalystAssessment(round(score, 1), label, notes)


def major_news_items(news: list[NewsItem]) -> list[NewsItem]:
    major: list[NewsItem] = []
    for item in news:
        title = item.title.lower()
        if is_low_value_headline(title):
            continue
        if any(contains_keyword(title, keyword) for keyword in MAJOR_NEWS_KEYWORDS):
            major.append(item)
    return major


def relevant_company_news(news: list[NewsItem], item: Analysis) -> list[NewsItem]:
    terms = relevance_terms(item.symbol, item.name)
    relevant = []
    for news_item in news:
        title = news_item.title.lower()
        if is_low_value_headline(title):
            continue
        if any(contains_keyword(title, term) for term in terms):
            relevant.append(news_item)
    return major_news_items(relevant)


def relevant_macro_news(news: list[NewsItem], symbol: str) -> list[NewsItem]:
    sector = SYMBOL_SECTORS.get(symbol.upper(), "")
    terms = SECTOR_MACRO_TERMS.get(sector, ())
    relevant: list[NewsItem] = []
    for item in news:
        title = item.title.lower()
        if is_low_value_headline(title):
            continue
        if contains_keyword(title, symbol.lower()) or any(contains_keyword(title, term) for term in terms):
            relevant.append(item)
    return major_news_items(relevant)


def non_low_value_news(news: list[NewsItem]) -> list[NewsItem]:
    return [item for item in news if not is_low_value_headline(item.title.lower())]


def is_low_value_headline(title: str) -> bool:
    return any(contains_keyword(title, phrase) for phrase in LOW_VALUE_NEWS_PHRASES)


def relevance_terms(symbol: str, name: str) -> tuple[str, ...]:
    terms = [] if symbol.upper() in AMBIGUOUS_SYMBOL_TERMS else [symbol.lower()]
    terms.extend(SYMBOL_ALIASES.get(symbol.upper(), ()))
    for token in re.findall(r"[a-zA-Z][a-zA-Z&]+", name.lower()):
        if len(token) >= 5 and token not in {"corporation", "company", "incorporated", "limited", "holdings", "group"}:
            terms.append(token)
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        cleaned = term.strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return tuple(unique)


def contains_keyword(text: str, keyword: str) -> bool:
    keyword = keyword.strip().lower()
    if not keyword:
        return False
    if len(keyword) <= 3 and keyword.isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text))
    return keyword in text


def keyword_hits(news: list[NewsItem], keywords: tuple[str, ...]) -> list[str]:
    text = " ".join(item.title.lower() for item in news)
    hits: list[str] = []
    for keyword in keywords:
        if contains_keyword(text, keyword):
            hits.append(keyword)
    return hits


def apply_catalyst_assessment(item: Analysis, weight: float, macro_shock: dict[str, float | bool | str] | None = None) -> None:
    assessment = assess_catalysts(relevant_company_news(item.news, item) + relevant_macro_news(item.macro_news or [], item.symbol), item.setup_direction)
    assessment = macro_adjusted_catalyst_score(item, assessment, macro_shock)
    item.catalyst_score = assessment.score
    item.catalyst_label = assessment.label
    item.catalyst_notes = assessment.notes
    base = item.setup_score if item.setup_score is not None else item.score
    item.final_trade_score = round(base * (1 - weight) + assessment.score * weight, 1)


def fetch_option_contract(symbol: str, side: str, price: float, min_dte: int = 21, max_dte: int = 45, provider: str = "tradier") -> OptionContract | None:
    if provider == "none":
        return None
    if provider == "nasdaq":
        try:
            return fetch_nasdaq_option_contract(symbol, side, price, min_dte, max_dte)
        except Exception:
            return None
    if provider == "yahoo":
        try:
            return fetch_yahoo_option_contract(symbol, side, price, min_dte, max_dte)
        except Exception:
            return None
    try:
        return fetch_tradier_option_contract(symbol, side, price, min_dte, max_dte)
    except Exception:
        if provider == "tradier":
            raise
    return None


def fetch_tradier_option_contract(symbol: str, side: str, price: float, min_dte: int = 21, max_dte: int = 45) -> OptionContract | None:
    payload = fetch_tradier_json(
        "/markets/options/expirations",
        {"symbol": symbol.upper(), "includeAllRoots": "true", "strikes": "false"},
    )
    dates = payload.get("expirations", {}).get("date") or []
    if isinstance(dates, str):
        dates = [dates]
    expiration = choose_expiration_date(dates, min_dte, max_dte)
    if expiration is None:
        return None

    chain_payload = fetch_tradier_json(
        "/markets/options/chains",
        {"symbol": symbol.upper(), "expiration": expiration.isoformat(), "greeks": "false"},
    )
    contracts = chain_payload.get("options", {}).get("option") or []
    if isinstance(contracts, dict):
        contracts = [contracts]
    side_name = "call" if side == "CALL" else "put"
    contracts = [contract for contract in contracts if str(contract.get("option_type", "")).lower() == side_name]
    if not contracts:
        return None

    target = price * (1.02 if side == "CALL" else 0.98)
    if side == "CALL":
        candidates = [contract for contract in contracts if as_float(contract.get("strike")) and as_float(contract.get("strike")) >= price]
    else:
        candidates = [contract for contract in contracts if as_float(contract.get("strike")) and as_float(contract.get("strike")) <= price]
    candidates = candidates or contracts
    chosen = min(candidates, key=lambda contract: abs((as_float(contract.get("strike")) or price) - target))
    return OptionContract(
        contract_symbol=str(chosen.get("symbol") or ""),
        side=side,
        strike=as_float(chosen.get("strike")) or 0.0,
        expiration=expiration,
        bid=as_float(chosen.get("bid")),
        ask=as_float(chosen.get("ask")),
        last_price=as_float(chosen.get("last")),
        volume=as_int(chosen.get("volume")),
        open_interest=as_int(chosen.get("open_interest")),
        implied_volatility=None,
    )


def fetch_nasdaq_option_contract(symbol: str, side: str, price: float, min_dte: int = 21, max_dte: int = 45) -> OptionContract | None:
    payload = fetch_nasdaq_json(symbol)
    rows = extract_nasdaq_option_rows(payload)
    if not rows:
        return None

    expirations = sorted({date for date in (parse_nasdaq_expiration(row) for row in rows) if date})
    expiration = choose_expiration_date([date.isoformat() for date in expirations], min_dte, max_dte)
    if expiration is None:
        return None

    prefix = "c_" if side == "CALL" else "p_"
    candidates: list[dict[str, Any]] = []
    for row in rows:
        row_expiration = parse_nasdaq_expiration(row)
        strike = parse_market_number(row.get("strike"))
        bid = parse_market_number(first_present(row, [f"{prefix}bid", f"{prefix}Bid", f"{prefix}bidprice"]))
        ask = parse_market_number(first_present(row, [f"{prefix}ask", f"{prefix}Ask", f"{prefix}askprice"]))
        last_price = parse_market_number(first_present(row, [f"{prefix}last", f"{prefix}Last", f"{prefix}lastprice"]))
        if row_expiration != expiration or strike is None:
            continue
        if bid is None and ask is None and last_price is None:
            continue
        row["_strike"] = strike
        candidates.append(row)

    if side == "CALL":
        directional = [row for row in candidates if row["_strike"] >= price]
        target = price * 1.02
    else:
        directional = [row for row in candidates if row["_strike"] <= price]
        target = price * 0.98
    directional = directional or candidates
    if not directional:
        return None

    chosen = min(directional, key=lambda row: abs(row["_strike"] - target))
    strike = chosen["_strike"]
    return OptionContract(
        contract_symbol=occ_symbol(symbol, expiration, side, strike),
        side=side,
        strike=strike,
        expiration=expiration,
        bid=parse_market_number(first_present(chosen, [f"{prefix}bid", f"{prefix}Bid", f"{prefix}bidprice"])),
        ask=parse_market_number(first_present(chosen, [f"{prefix}ask", f"{prefix}Ask", f"{prefix}askprice"])),
        last_price=parse_market_number(first_present(chosen, [f"{prefix}last", f"{prefix}Last", f"{prefix}lastprice"])),
        volume=parse_market_int(first_present(chosen, [f"{prefix}volume", f"{prefix}Volume"])),
        open_interest=parse_market_int(first_present(chosen, [f"{prefix}openinterest", f"{prefix}openInterest", f"{prefix}Openinterest"])),
        implied_volatility=parse_market_number(first_present(chosen, [f"{prefix}iv", f"{prefix}IV", f"{prefix}impliedvolatility"])),
    )


def extract_nasdaq_option_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    table = data.get("table") or {}
    rows = table.get("rows") or data.get("rows") or []
    return rows if isinstance(rows, list) else []


def parse_nasdaq_expiration(row: dict[str, Any]) -> dt.date | None:
    raw = first_present(row, ["expiryDate", "expirydate", "expirationDate", "expiration", "expirygroup"])
    if raw is None:
        return None
    text = str(raw).strip()
    for prefix in ("Expires ", "Exp "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    text = text.replace(",", "")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d %Y", "%B %d %Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    for fmt in ("%b %d", "%B %d"):
        try:
            parsed = dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        today = dt.datetime.now().astimezone().date()
        inferred = parsed.replace(year=today.year)
        if inferred < today:
            inferred = inferred.replace(year=today.year + 1)
        return inferred
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def first_present(row: dict[str, Any], keys: list[str]) -> Any:
    normalized = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "--", "N/A"):
            return value
        value = normalized.get(key.lower())
        if value not in (None, "", "--", "N/A"):
            return value
    return None


def parse_market_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace("$", "").replace(",", "").replace("%", "").strip()
    if not text or text in {"--", "N/A"}:
        return None
    return as_float(text)


def parse_market_int(value: Any) -> int | None:
    number = parse_market_number(value)
    if number is None:
        return None
    return int(number)


def fetch_yahoo_option_contract(symbol: str, side: str, price: float, min_dte: int = 21, max_dte: int = 45) -> OptionContract | None:
    encoded = urllib.parse.quote(symbol.upper())
    base_url = f"https://query2.finance.yahoo.com/v7/finance/options/{encoded}"
    payload = fetch_json(base_url)
    result = (payload.get("optionChain", {}).get("result") or [])
    if not result:
        return None

    expirations = result[0].get("expirationDates") or []
    expiration = choose_expiration(expirations, min_dte, max_dte)
    if expiration is None:
        return None

    chain_payload = fetch_json(f"{base_url}?date={expiration}")
    chain_result = (chain_payload.get("optionChain", {}).get("result") or [])
    if not chain_result:
        return None

    options = (chain_result[0].get("options") or [{}])[0]
    contracts = options.get("calls" if side == "CALL" else "puts") or []
    if not contracts:
        return None

    target = price * (1.02 if side == "CALL" else 0.98)
    if side == "CALL":
        candidates = [contract for contract in contracts if as_float(contract.get("strike")) and as_float(contract.get("strike")) >= price]
    else:
        candidates = [contract for contract in contracts if as_float(contract.get("strike")) and as_float(contract.get("strike")) <= price]
    candidates = candidates or contracts
    chosen = min(candidates, key=lambda contract: abs((as_float(contract.get("strike")) or price) - target))
    expiration_date = dt.datetime.fromtimestamp(expiration, tz=dt.timezone.utc).date()
    return OptionContract(
        contract_symbol=str(chosen.get("contractSymbol") or ""),
        side=side,
        strike=as_float(chosen.get("strike")) or 0.0,
        expiration=expiration_date,
        bid=as_float(chosen.get("bid")),
        ask=as_float(chosen.get("ask")),
        last_price=as_float(chosen.get("lastPrice")),
        volume=as_int(chosen.get("volume")),
        open_interest=as_int(chosen.get("openInterest")),
        implied_volatility=as_float(chosen.get("impliedVolatility")),
    )


def choose_expiration_date(dates: list[str], min_dte: int, max_dte: int) -> dt.date | None:
    today = dt.datetime.now().astimezone().date()
    choices: list[tuple[int, dt.date]] = []
    for raw in dates:
        try:
            expiration = dt.date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        choices.append(((expiration - today).days, expiration))
    in_range = [choice for choice in choices if min_dte <= choice[0] <= max_dte]
    if in_range:
        return min(in_range, key=lambda choice: choice[0])[1]
    future = [choice for choice in choices if choice[0] > 0]
    if not future:
        return None
    return min(future, key=lambda choice: abs(choice[0] - min_dte))[1]


def estimate_option_contract(symbol: str, side: str, price: float, min_dte: int = 21) -> OptionContract:
    expiration = next_friday_after(min_dte)
    target = price * (1.02 if side == "CALL" else 0.98)
    increment = strike_increment(price)
    if side == "CALL":
        strike = math.ceil(target / increment) * increment
    else:
        strike = math.floor(target / increment) * increment
    strike = round(strike, 2)
    return OptionContract(
        contract_symbol=occ_symbol(symbol, expiration, side, strike),
        side=side,
        strike=strike,
        expiration=expiration,
        bid=None,
        ask=None,
        last_price=None,
        volume=None,
        open_interest=None,
        implied_volatility=None,
        estimated=True,
    )


def next_friday_after(min_dte: int) -> dt.date:
    date = dt.datetime.now().astimezone().date() + dt.timedelta(days=min_dte)
    days_until_friday = (4 - date.weekday()) % 7
    return date + dt.timedelta(days=days_until_friday)


def strike_increment(price: float) -> float:
    if price < 25:
        return 0.5
    if price < 100:
        return 1.0
    if price < 250:
        return 2.5
    if price < 500:
        return 5.0
    return 10.0


def occ_symbol(symbol: str, expiration: dt.date, side: str, strike: float) -> str:
    code = "C" if side == "CALL" else "P"
    strike_code = int(round(strike * 1000))
    return f"{symbol.upper()}{expiration:%y%m%d}{code}{strike_code:08d}"


def choose_expiration(expirations: list[int], min_dte: int, max_dte: int) -> int | None:
    today = dt.datetime.now(dt.timezone.utc).date()
    choices: list[tuple[int, int]] = []
    for expiration in expirations:
        expiration_date = dt.datetime.fromtimestamp(expiration, tz=dt.timezone.utc).date()
        dte = (expiration_date - today).days
        choices.append((dte, expiration))
    in_range = [choice for choice in choices if min_dte <= choice[0] <= max_dte]
    if in_range:
        return min(in_range, key=lambda choice: choice[0])[1]
    future = [choice for choice in choices if choice[0] > 0]
    if not future:
        return None
    return min(future, key=lambda choice: abs(choice[0] - min_dte))[1]


def chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def normal_yield(value: Any) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return number / 100 if number > 1 else number


def pct_change(values: list[float], days: int) -> float | None:
    if len(values) <= days or values[-days - 1] == 0:
        return None
    return values[-1] / values[-days - 1] - 1


def moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return statistics.fmean(values[-window:])


def daily_returns(values: list[float]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(values, values[1:]):
        if previous:
            returns.append(current / previous - 1)
    return returns


def annualized_volatility(values: list[float]) -> float | None:
    returns = daily_returns(values)
    if len(returns) < 30:
        return None
    return statistics.stdev(returns) * math.sqrt(252)


def realized_volatility(values: list[float]) -> float | None:
    returns = daily_returns(values)
    if len(returns) < 5:
        return None
    return statistics.stdev(returns)


def max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            worst = min(worst, value / peak - 1)
    return worst


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[-period - 1 :], values[-period:]):
        change = current - previous
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    average_gain = statistics.fmean(gains)
    average_loss = statistics.fmean(losses)
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_momentum(return_1y: float | None, return_6m: float | None, return_3m: float | None, sma_50: float | None, sma_200: float | None, price: float) -> float:
    score = 50.0
    if return_1y is not None:
        score += return_1y * 80
    if return_6m is not None:
        score += return_6m * 70
    if return_3m is not None:
        score += return_3m * 45
    if sma_50 and price > sma_50:
        score += 8
    if sma_200 and price > sma_200:
        score += 10
    if sma_50 and sma_200 and sma_50 > sma_200:
        score += 8
    return clamp(score)


def score_value(pe: float | None) -> float:
    if pe is None or pe <= 0:
        return 50.0
    if pe <= 12:
        return 90.0
    if pe <= 20:
        return 80.0
    if pe <= 30:
        return 65.0
    if pe <= 45:
        return 45.0
    return 25.0


def score_risk(volatility: float | None, drawdown: float | None, beta: float | None) -> float:
    score = 75.0
    if volatility is not None:
        score -= max(0, volatility - 0.18) * 120
        score += max(0, 0.18 - volatility) * 80
    if drawdown is not None:
        score += drawdown * 80
    if beta is not None:
        score -= max(0, beta - 1) * 12
        score += max(0, 1 - beta) * 6
    return clamp(score)


def score_yield(dividend_yield: float | None) -> float:
    if dividend_yield is None:
        return 45.0
    if dividend_yield <= 0:
        return 40.0
    if dividend_yield <= 0.05:
        return 50 + dividend_yield * 900
    return 70.0


def score_short_term_setup(series: PriceSeries) -> tuple[float, str, list[str], str]:
    values = series.closes
    volumes = series.volumes
    price = values[-1]
    sma_10 = moving_average(values, 10)
    sma_20 = moving_average(values, 20)
    sma_50 = moving_average(values, 50)
    return_1d = pct_change(values, 1)
    return_5d = pct_change(values, 5)
    return_20d = pct_change(values, 20)
    recent_rsi = rsi(values)
    vol_10 = realized_volatility(values[-11:])
    vol_50 = realized_volatility(values[-51:])
    high_20 = max(values[-21:-1]) if len(values) > 21 else None
    high_60 = max(values[-61:-1]) if len(values) > 61 else None
    low_20 = min(values[-20:]) if len(values) >= 20 else None
    prior_low_20 = min(values[-21:-1]) if len(values) > 21 else None
    low_60 = min(values[-61:-1]) if len(values) > 61 else None
    avg_volume_20 = statistics.fmean(volumes[-21:-1]) if len(volumes) > 21 else None
    volume_ratio = (volumes[-1] / avg_volume_20) if avg_volume_20 else None

    bull_score = 0.0
    bull_notes: list[str] = []
    if sma_10 and sma_20 and sma_50 and price > sma_10 > sma_20 > sma_50:
        bull_score += 18
        bull_notes.append("stacked 10/20/50-day uptrend")
    elif sma_20 and sma_50 and price > sma_20 > sma_50:
        bull_score += 12
        bull_notes.append("clean 20/50-day uptrend")

    if high_20 and price >= high_20 * 0.995:
        bull_score += 18
        bull_notes.append("testing or breaking 20-day high")
    if high_60 and price >= high_60 * 0.985:
        bull_score += 12
        bull_notes.append("near 60-day high")

    if volume_ratio is not None:
        if volume_ratio >= 2:
            bull_score += 18
            bull_notes.append("major volume expansion")
        elif volume_ratio >= 1.35:
            bull_score += 12
            bull_notes.append("above-average volume")

    if vol_10 is not None and vol_50 is not None and vol_10 < vol_50 * 0.75:
        bull_score += 16
        bull_notes.append("volatility squeeze")

    if low_20 and high_20 and low_20 > 0:
        range_width = high_20 / low_20 - 1
        if range_width <= 0.12:
            bull_score += 12
            bull_notes.append("tight 20-day consolidation")
        elif range_width <= 0.20:
            bull_score += 6
            bull_notes.append("moderate consolidation")

    if return_5d is not None:
        if 0.01 <= return_5d <= 0.12:
            bull_score += 10
            bull_notes.append("healthy 5-day strength")
        elif return_5d > 0.18:
            bull_score -= 8
            bull_notes.append("extended short-term move")

    if return_20d is not None:
        if 0.03 <= return_20d <= 0.30:
            bull_score += 8
            bull_notes.append("strong 20-day momentum")
        elif return_20d > 0.45:
            bull_score -= 10
            bull_notes.append("possibly overheated 20-day move")

    if return_1d is not None and return_1d < -0.04:
        bull_score -= 8
        bull_notes.append("sharp red day")

    if recent_rsi is not None:
        if 45 <= recent_rsi <= 68:
            bull_score += 8
            bull_notes.append("RSI in constructive zone")
        elif recent_rsi > 78:
            bull_score -= 15
            bull_notes.append("RSI very overbought")

    bear_score = 0.0
    bear_notes: list[str] = []
    if sma_10 and sma_20 and sma_50 and price < sma_10 < sma_20 < sma_50:
        bear_score += 18
        bear_notes.append("stacked 10/20/50-day downtrend")
    elif sma_20 and sma_50 and price < sma_20 < sma_50:
        bear_score += 12
        bear_notes.append("clean 20/50-day downtrend")

    if prior_low_20 and price <= prior_low_20 * 1.005:
        bear_score += 18
        bear_notes.append("testing or breaking 20-day low")
    if low_60 and price <= low_60 * 1.015:
        bear_score += 12
        bear_notes.append("near 60-day low")

    if volume_ratio is not None:
        if volume_ratio >= 2:
            bear_score += 18
            bear_notes.append("major volume expansion")
        elif volume_ratio >= 1.35:
            bear_score += 12
            bear_notes.append("above-average volume")

    if vol_10 is not None and vol_50 is not None and vol_10 < vol_50 * 0.75:
        bear_score += 16
        bear_notes.append("volatility squeeze")

    if low_20 and high_20 and low_20 > 0:
        range_width = high_20 / low_20 - 1
        if range_width <= 0.12:
            bear_score += 12
            bear_notes.append("tight 20-day consolidation")
        elif range_width <= 0.20:
            bear_score += 6
            bear_notes.append("moderate consolidation")

    if return_5d is not None:
        if -0.12 <= return_5d <= -0.01:
            bear_score += 10
            bear_notes.append("healthy 5-day weakness")
        elif return_5d < -0.18:
            bear_score -= 8
            bear_notes.append("extended downside move")

    if return_20d is not None:
        if -0.30 <= return_20d <= -0.03:
            bear_score += 8
            bear_notes.append("strong 20-day downside momentum")
        elif return_20d < -0.45:
            bear_score -= 10
            bear_notes.append("possibly oversold 20-day move")

    if return_1d is not None and return_1d > 0.04:
        bear_score -= 8
        bear_notes.append("sharp green day")

    if recent_rsi is not None:
        if 32 <= recent_rsi <= 55:
            bear_score += 8
            bear_notes.append("RSI in bearish trigger zone")
        elif recent_rsi < 22:
            bear_score -= 15
            bear_notes.append("RSI very oversold")

    direction = "CALL" if bull_score >= bear_score else "PUT"
    score = clamp(max(bull_score, bear_score))
    notes = bull_notes if direction == "CALL" else bear_notes
    if score >= 78:
        label = "A setup"
    elif score >= 62:
        label = "B setup"
    elif score >= 48:
        label = "Watch setup"
    else:
        label = "No clean setup"
    return round(score, 1), label, notes or ["no clean short-term setup"], direction


def linear_slope(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    x_mean = (len(values) - 1) / 2
    y_mean = statistics.fmean(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    if not denominator:
        return None
    return sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values)) / denominator


def major_level_notes(highs: list[float], lows: list[float], price: float, direction: str) -> tuple[float, list[str]]:
    score = 0.0
    notes: list[str] = []
    windows = ((60, 8), (120, 12), (252, 16))
    for window, points in windows:
        if len(lows) <= window or len(highs) <= window:
            continue
        if direction == "CALL":
            support = min(lows[-window - 1 : -1])
            if support > 0 and price <= support * 1.035:
                score = max(score, float(points))
                notes = [f"near major {window}-day support"]
        elif direction == "PUT":
            resistance = max(highs[-window - 1 : -1])
            if resistance > 0 and price >= resistance * 0.965:
                score = max(score, float(points))
                notes = [f"near major {window}-day resistance"]
    return score, notes


def wedge_compression_notes(highs: list[float], lows: list[float], direction: str) -> tuple[float, list[str]]:
    if len(highs) < 45 or len(lows) < 45:
        return 0.0, []
    recent_highs = highs[-21:]
    recent_lows = lows[-21:]
    prior_highs = highs[-42:-21]
    prior_lows = lows[-42:-21]
    recent_range = max(recent_highs) - min(recent_lows)
    prior_range = max(prior_highs) - min(prior_lows)
    if prior_range <= 0 or recent_range > prior_range * 0.82:
        return 0.0, []
    high_slope = linear_slope(recent_highs)
    low_slope = linear_slope(recent_lows)
    if high_slope is None or low_slope is None:
        return 0.0, []
    if direction == "CALL" and high_slope < 0 and low_slope < 0 and abs(high_slope) > abs(low_slope):
        return 12.0, ["falling wedge compression"]
    if direction == "PUT" and high_slope > 0 and low_slope > 0 and abs(low_slope) > abs(high_slope):
        return 12.0, ["rising wedge compression"]
    if recent_range <= prior_range * 0.65:
        return 6.0, ["volatility compression near reversal zone"]
    return 0.0, []


def candle_rejection_notes(opens: list[float], highs: list[float], lows: list[float], closes: list[float], direction: str) -> tuple[float, list[str]]:
    if len(closes) < 2:
        return 0.0, []
    open_price = opens[-1]
    high = highs[-1]
    low = lows[-1]
    close = closes[-1]
    prev_open = opens[-2]
    prev_close = closes[-2]
    day_range = high - low
    if day_range <= 0:
        return 0.0, []
    body = abs(close - open_price)
    lower_wick = min(open_price, close) - low
    upper_wick = high - max(open_price, close)
    if direction == "CALL":
        if lower_wick >= body * 1.8 and close >= low + day_range * 0.58:
            return 8.0, ["bullish candle rejection"]
        if close > open_price and open_price <= prev_close and close >= prev_open:
            return 7.0, ["bullish engulfing attempt"]
    if direction == "PUT":
        if upper_wick >= body * 1.8 and close <= low + day_range * 0.42:
            return 8.0, ["bearish candle rejection"]
        if close < open_price and open_price >= prev_close and close <= prev_open:
            return 7.0, ["bearish engulfing attempt"]
    return 0.0, []


def preferred_pattern_notes(highs: list[float], lows: list[float], closes: list[float], direction: str) -> tuple[float, list[str]]:
    if len(closes) < 35 or len(highs) < 35 or len(lows) < 35:
        return 0.0, []
    score = 0.0
    notes: list[str] = []
    window = 34
    offset = len(closes) - window
    h = highs[-window:]
    l = lows[-window:]
    c = closes[-window:]
    price = closes[-1]
    atr = average_true_range(highs[-window:], lows[-window:], closes[-window:]) or price * 0.025
    height = max(h) - min(l)
    if height <= 0:
        return 0.0, []

    def pivot_highs(radius: int = 2) -> list[tuple[int, float]]:
        points: list[tuple[int, float]] = []
        for index in range(radius, len(h) - radius):
            value = h[index]
            if value == max(h[index - radius : index + radius + 1]):
                points.append((offset + index, value))
        return points

    def pivot_lows(radius: int = 2) -> list[tuple[int, float]]:
        points: list[tuple[int, float]] = []
        for index in range(radius, len(l) - radius):
            value = l[index]
            if value == min(l[index - radius : index + radius + 1]):
                points.append((offset + index, value))
        return points

    ph = pivot_highs()
    pl = pivot_lows()

    def slope(points: list[tuple[int, float]]) -> float | None:
        if len(points) < 2:
            return None
        return (points[-1][1] - points[0][1]) / max(1, points[-1][0] - points[0][0])

    high_slope = slope(ph[-3:])
    low_slope = slope(pl[-3:])
    old_range = max(h[:12]) - min(l[:12])
    new_range = max(h[-12:]) - min(l[-12:])
    contraction = old_range > 0 and new_range <= old_range * 0.50
    enough_touches = len(ph) >= 2 and len(pl) >= 2

    if enough_touches and high_slope is not None and low_slope is not None:
        min_slope = max(price * 0.0010, atr * 0.035)
        if direction == "CALL":
            recent_high_points = ph[-3:] if len(ph) >= 3 else ph[-2:]
            recent_low_points = pl[-3:] if len(pl) >= 3 else pl[-2:]
            flat_highs = (max(point[1] for point in recent_high_points) - min(point[1] for point in recent_high_points)) <= max(atr * 0.45, price * 0.006)
            touches_spread = recent_high_points[-1][0] - recent_high_points[0][0] >= 7
            lows_rising = (
                len(recent_low_points) >= 2
                and recent_low_points[-1][1] > recent_low_points[0][1] + max(atr * 1.0, price * 0.012)
                and all(later[1] > earlier[1] for earlier, later in zip(recent_low_points, recent_low_points[1:]))
            )
            resistance = statistics.fmean(point[1] for point in recent_high_points)
            price_near_ceiling = resistance * 0.985 <= price <= resistance * 1.018
            if flat_highs and touches_spread and lows_rising and price_near_ceiling:
                score += 28
                notes.append("definitive ascending triangle")
            if high_slope < -min_slope and low_slope < -min_slope * 0.35 and abs(high_slope) > abs(low_slope) * 1.45 and contraction:
                score += 26
                notes.append("definitive falling wedge")
        elif direction == "PUT":
            recent_high_points = ph[-3:] if len(ph) >= 3 else ph[-2:]
            recent_low_points = pl[-3:] if len(pl) >= 3 else pl[-2:]
            support_closes = closes[-4:]
            support_level = statistics.median(support_closes)
            flat_lows = max(abs(close - support_level) for close in support_closes[-3:]) <= max(atr * 0.45, price * 0.012)
            wick_respect = min(lows[-4:]) >= support_level - max(atr * 1.25, price * 0.025)
            touches_spread = recent_high_points[-1][0] - recent_high_points[0][0] >= 7
            highs_falling = (
                len(recent_high_points) >= 2
                and recent_high_points[-1][1] < recent_high_points[0][1] - max(atr * 1.0, price * 0.012)
                and all(later[1] < earlier[1] for earlier, later in zip(recent_high_points, recent_high_points[1:]))
            )
            price_near_floor = support_level * 0.985 <= price <= support_level * 1.015
            if len(recent_high_points) >= 3 and flat_lows and wick_respect and touches_spread and highs_falling and price_near_floor:
                score += 28
                notes.append("definitive descending triangle")
            if high_slope > min_slope * 0.35 and low_slope > min_slope and abs(low_slope) > abs(high_slope) * 1.45 and contraction:
                score += 26
                notes.append("definitive rising wedge")

    flagpole = pct_change(closes, 24)
    consolidation = enough_touches and contraction and high_slope is not None and low_slope is not None and high_slope < 0 < low_slope
    if consolidation and flagpole is not None:
        if direction == "CALL" and flagpole >= 0.12:
            score += 24
            notes.append("definitive bullish pennant")
        elif direction == "PUT" and flagpole <= -0.12:
            score += 24
            notes.append("definitive bearish pennant")

    if direction == "CALL" and len(lows) >= 30 and len(highs) >= 30:
        left_shoulder = min(lows[-30:-20])
        head = min(lows[-20:-10])
        right_shoulder = min(lows[-10:])
        neckline_left = max(highs[-24:-14])
        neckline_right = max(highs[-12:])
        shoulder_balance = abs(left_shoulder - right_shoulder) <= max(atr * 1.0, price * 0.025)
        head_depth = min(left_shoulder, right_shoulder) - head
        neckline_balance = abs(neckline_left - neckline_right) <= max(atr * 1.2, price * 0.03)
        neckline_near = price >= min(neckline_left, neckline_right) * 0.98
        right_side_holding = closes[-1] > right_shoulder + atr * 0.65
        if shoulder_balance and head_depth >= max(atr * 1.5, price * 0.035) and neckline_balance and neckline_near and right_side_holding:
            score += 30
            notes.append("definitive inverse head-and-shoulders")

    return score, notes


def prioritize_pattern_notes(notes: list[str]) -> list[str]:
    preferred_terms = ("inverse head-and-shoulders", "pennant", "ascending triangle", "descending triangle", "wedge")
    return sorted(
        notes,
        key=lambda note: (
            1 if "no preferred" in note else 0,
            0 if any(term in note for term in preferred_terms) else 1,
        ),
    )


def two_line_pattern_notes(highs: list[float], lows: list[float], closes: list[float]) -> tuple[float, list[str], str]:
    if min(len(highs), len(lows), len(closes)) < 24:
        return 0.0, [], ""
    window = min(42, len(closes))
    offset = len(closes) - window
    h = highs[-window:]
    l = lows[-window:]
    c = closes[-window:]
    price = closes[-1]
    atr = average_true_range(highs[-window:], lows[-window:], closes[-window:]) or price * 0.025
    span = max(h) - min(l)
    if span <= 0:
        return 0.0, [], ""

    def pivots(values: list[float], mode: str, radius: int = 2) -> list[tuple[int, float]]:
        points: list[tuple[int, float]] = []
        for index in range(radius, len(values) - radius):
            window_values = values[index - radius : index + radius + 1]
            value = values[index]
            if mode == "high" and value == max(window_values):
                points.append((offset + index, value))
            elif mode == "low" and value == min(window_values):
                points.append((offset + index, value))
        return points

    high_points = pivots(h, "high")
    low_points = pivots(l, "low")
    if len(high_points) < 2:
        high_points = [(offset, h[0]), (len(closes) - 1, h[-1])]
    if len(low_points) < 2:
        low_points = [(offset, l[0]), (len(closes) - 1, l[-1])]
    high_points = high_points[-3:]
    low_points = low_points[-3:]

    def slope(points: list[tuple[int, float]]) -> float:
        return (points[-1][1] - points[0][1]) / max(1, points[-1][0] - points[0][0])

    high_slope = slope(high_points)
    low_slope = slope(low_points)
    min_slope = max(price * 0.00045, atr * 0.015)
    flat_tolerance = max(atr * 1.15, price * 0.018)
    high_band = max(point[1] for point in high_points) - min(point[1] for point in high_points)
    low_band = max(point[1] for point in low_points) - min(point[1] for point in low_points)
    recent_range = max(h[-12:]) - min(l[-12:])
    older_range = max(h[:12]) - min(l[:12])
    contracting = older_range > 0 and recent_range <= older_range * 0.86
    flagpole = pct_change(closes, 24) or 0.0

    notes: list[str] = []
    direction = ""
    score = 0.0

    resistance = statistics.fmean(point[1] for point in high_points)
    support_floor = statistics.median(closes[-4:]) if len(closes) >= 4 else statistics.fmean(point[1] for point in low_points)

    if high_band <= flat_tolerance and low_slope > min_slope and price >= resistance * 0.955:
        notes.append("two-line ascending triangle")
        return 76.0, notes, "CALL"

    if high_slope < -min_slope and abs(price - support_floor) <= max(atr * 1.4, price * 0.03):
        notes.append("two-line descending triangle")
        return 76.0, notes, "PUT"

    if high_slope < -min_slope and low_slope < -min_slope * 0.15 and abs(high_slope) > abs(low_slope) * 1.15 and contracting:
        notes.append("two-line falling wedge")
        return 74.0, notes, "CALL"

    if high_slope > min_slope * 0.15 and low_slope > min_slope and abs(low_slope) > abs(high_slope) * 1.15 and contracting:
        notes.append("two-line rising wedge")
        return 74.0, notes, "PUT"

    if high_slope < -min_slope and low_slope > min_slope and contracting:
        if flagpole >= 0.05:
            notes.append("two-line bullish pennant")
            direction = "CALL"
        elif flagpole <= -0.05:
            notes.append("two-line bearish pennant")
            direction = "PUT"
        else:
            notes.append("two-line pennant compression")
            direction = "CALL" if closes[-1] >= closes[-5] else "PUT"
        return 72.0, notes, direction

    return score, notes, direction


def pivot_points(values: list[float], mode: str, radius: int = 2, start: int = 0, end: int | None = None) -> list[tuple[int, float]]:
    end = len(values) if end is None else min(end, len(values))
    points: list[tuple[int, float]] = []
    for index in range(max(radius, start), end - radius):
        window = values[index - radius : index + radius + 1]
        value = values[index]
        if mode == "high" and value == max(window):
            points.append((index, value))
        elif mode == "low" and value == min(window):
            points.append((index, value))
    return points


def line_from_points(points: list[tuple[int, float]]) -> tuple[float, float] | None:
    if len(points) < 2:
        return None
    x_mean = statistics.fmean(point[0] for point in points)
    y_mean = statistics.fmean(point[1] for point in points)
    denominator = sum((point[0] - x_mean) ** 2 for point in points)
    if denominator <= 0:
        return None
    slope = sum((point[0] - x_mean) * (point[1] - y_mean) for point in points) / denominator
    intercept = y_mean - slope * x_mean
    return slope, intercept


def line_value(line: tuple[float, float], index: int) -> float:
    return line[0] * index + line[1]


def average_body(opens: list[float], closes: list[float], end_index: int, window: int = 20) -> float | None:
    start = max(0, end_index - window)
    bodies = [abs(closes[index] - opens[index]) for index in range(start, end_index)]
    if not bodies:
        return None
    return statistics.fmean(bodies)


def average_volume(volumes: list[int], end_index: int, window: int = 20) -> float | None:
    start = max(0, end_index - window)
    sample = [volume for volume in volumes[start:end_index] if volume is not None]
    if not sample:
        return None
    return statistics.fmean(sample)


def detect_breakout_candle(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
    upper_line: tuple[float, float],
    lower_line: tuple[float, float],
    start_index: int,
    end_index: int,
) -> tuple[int | None, str, float | None]:
    for index in range(end_index + 1, len(closes)):
        avg_body = average_body(opens, closes, index)
        avg_vol = average_volume(volumes, index)
        if not avg_body or not avg_vol:
            continue
        body = abs(closes[index] - opens[index])
        volume_ratio = volumes[index] / avg_vol if avg_vol else None
        if body <= avg_body * 1.3 or volume_ratio is None or volume_ratio <= 1.5:
            continue
        upper = line_value(upper_line, index)
        lower = line_value(lower_line, index)
        if closes[index] > upper and closes[index] > opens[index]:
            return index, "CALL", volume_ratio
        if closes[index] < lower and closes[index] < opens[index]:
            return index, "PUT", volume_ratio
    return None, "", None


def latest_breakout_candle(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
    upper_line: tuple[float, float],
    lower_line: tuple[float, float],
) -> tuple[int | None, str, float | None]:
    index = len(closes) - 1
    avg_body = average_body(opens, closes, index)
    avg_vol = average_volume(volumes, index)
    if not avg_body or not avg_vol:
        return None, "", None
    body = abs(closes[index] - opens[index])
    volume_ratio = volumes[index] / avg_vol if avg_vol else None
    if body <= avg_body * 1.3 or volume_ratio is None or volume_ratio <= 1.5:
        return None, "", volume_ratio
    upper = line_value(upper_line, index)
    lower = line_value(lower_line, index)
    if closes[index] > upper and closes[index] > opens[index]:
        return index, "CALL", volume_ratio
    if closes[index] < lower and closes[index] < opens[index]:
        return index, "PUT", volume_ratio
    return None, "", volume_ratio


def detect_chart_pattern(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
) -> PatternDetection | None:
    usable = min(len(opens), len(highs), len(lows), len(closes), len(volumes))
    if usable < 35:
        return None
    opens = opens[-usable:]
    highs = highs[-usable:]
    lows = lows[-usable:]
    closes = closes[-usable:]
    volumes = volumes[-usable:]
    candidates: list[PatternDetection] = []
    windows = (18, 22, 26, 30, 34, 38, 42)
    for window in windows:
        if usable < window + 2:
            continue
        start = usable - window
        end = usable - 1
        high_pivots = pivot_points(highs, "high", start=start, end=end + 1)
        low_pivots = pivot_points(lows, "low", start=start, end=end + 1)
        if len(high_pivots) < 2 or len(low_pivots) < 2:
            continue
        high_pivots = high_pivots[-3:]
        low_pivots = low_pivots[-3:]
        upper_line = line_from_points(high_pivots)
        lower_line = line_from_points(low_pivots)
        if upper_line is None or lower_line is None:
            continue
        upper_slope, _upper_intercept = upper_line
        lower_slope, _lower_intercept = lower_line
        slope_floor = max((average_true_range(highs[start:end + 1], lows[start:end + 1], closes[start:end + 1]) or closes[-1] * 0.02) * 0.02, closes[-1] * 0.00025)
        slope_ratio = max(abs(upper_slope), abs(lower_slope)) / max(slope_floor, min(abs(upper_slope), abs(lower_slope)))
        if slope_ratio > 4.0:
            continue
        start_width = line_value(upper_line, start) - line_value(lower_line, start)
        end_width = line_value(upper_line, end) - line_value(lower_line, end)
        if start_width <= 0:
            continue
        convergence = clamp((1 - (end_width / start_width)) * 100, 0, 100)
        if end_width <= 0 or convergence < 16 or convergence > 88:
            continue
        atr = average_true_range(highs[start:end + 1], lows[start:end + 1], closes[start:end + 1]) or closes[-1] * 0.02
        if start_width < atr * 1.2 or end_width < atr * 0.35:
            continue
        flat_tolerance = max(atr * 0.55, closes[-1] * 0.008)
        upper_range = max(point[1] for point in high_pivots) - min(point[1] for point in high_pivots)
        lower_range = max(point[1] for point in low_pivots) - min(point[1] for point in low_pivots)
        flagpole = pct_change(closes[: end + 1], min(12, end)) or 0.0
        breakout_index, breakout_direction, volume_ratio = latest_breakout_candle(
            opens, highs, lows, closes, volumes, upper_line, lower_line
        )

        pattern_type = ""
        direction = ""
        shape_score = 0.0
        if upper_slope > 0 and lower_slope > 0 and lower_slope > upper_slope and convergence >= 18:
            pattern_type = "Rising wedge"
            direction = "PUT"
            shape_score = 34
        elif upper_slope < 0 and lower_slope < 0 and upper_slope < lower_slope and convergence >= 18:
            pattern_type = "Falling wedge"
            direction = "CALL"
            shape_score = 34
        elif upper_slope < 0 and lower_slope > 0 and convergence >= 24 and flagpole >= 0.05:
            pattern_type = "Bull pennant"
            direction = "CALL"
            shape_score = 36
        elif upper_slope < 0 and lower_slope > 0 and convergence >= 24 and flagpole <= -0.05:
            pattern_type = "Bear pennant"
            direction = "PUT"
            shape_score = 36
        elif upper_range <= flat_tolerance and lower_slope > 0:
            pattern_type = "Breakout candle"
            direction = "CALL"
            shape_score = 30
        elif lower_range <= flat_tolerance and upper_slope < 0:
            pattern_type = "Breakdown candle"
            direction = "PUT"
            shape_score = 30
        if not pattern_type:
            continue

        if breakout_direction and direction != breakout_direction:
            continue

        trigger_line = upper_line if direction == "CALL" else lower_line
        trigger_price = line_value(trigger_line, end)
        trigger_distance = abs(closes[-1] - trigger_price)
        proximity_score = max(0.0, 1 - (trigger_distance / max(atr * 2.5, closes[-1] * 0.01))) * 20
        if breakout_index is None and proximity_score < 8:
            continue
        volume_score = min(14, max(0.0, ((volume_ratio or 1.0) - 1.0) * 10))
        breakout_score = 16 if breakout_index is not None else 0
        confidence = clamp(
            shape_score
            + min(24, convergence * 0.24)
            + proximity_score
            + volume_score
            + breakout_score,
            0,
            100,
        )
        if confidence < 70:
            continue
        candidates.append(
            PatternDetection(
                pattern_type=pattern_type,
                direction=direction,
                start_index=start,
                end_index=end,
                upper_start=high_pivots[0],
                upper_end=high_pivots[-1],
                lower_start=low_pivots[0],
                lower_end=low_pivots[-1],
                upper_slope=upper_slope,
                lower_slope=lower_slope,
                convergence_score=round(convergence, 1),
                breakout_index=breakout_index,
                breakout_volume_ratio=round(volume_ratio or 0, 2),
                confidence=round(confidence, 1),
            )
        )
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda candidate: (
            round(candidate.confidence, 2),
            candidate.end_index - candidate.start_index,
            len(candidate.pivot_highs or []) + len(candidate.pivot_lows or []),
        ),
        reverse=True,
    )[0]


def significant_swings(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    start: int,
    end: int,
    radius: int = 2,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    atr = average_true_range(highs[start : end + 1], lows[start : end + 1], closes[start : end + 1]) or closes[-1] * 0.02
    min_move = max(atr * 0.55, closes[-1] * 0.006)
    high_points = pivot_points(highs, "high", radius=radius, start=start, end=end + 1)
    low_points = pivot_points(lows, "low", radius=radius, start=start, end=end + 1)

    def filter_points(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
        filtered: list[tuple[int, float]] = []
        for point in points:
            if not filtered:
                filtered.append(point)
                continue
            if point[0] - filtered[-1][0] < 3:
                if abs(point[1] - filtered[-1][1]) > min_move:
                    filtered[-1] = point
                continue
            if abs(point[1] - filtered[-1][1]) >= min_move:
                filtered.append(point)
        return filtered

    return filter_points(high_points), filter_points(low_points)


def best_visual_line(
    points: list[tuple[int, float]],
    fallback: tuple[int, float],
    prefer_recent: bool = True,
    min_start_index: int | None = None,
) -> tuple[tuple[int, float], tuple[int, float]] | None:
    if len(points) >= 2:
        candidates: list[tuple[float, tuple[int, float], tuple[int, float]]] = []
        pool = points[-4:] if prefer_recent else points
        if min_start_index is not None:
            pool = [point for point in pool if point[0] >= min_start_index]
        for first_index in range(len(pool) - 1):
            for second_index in range(first_index + 1, len(pool)):
                first = pool[first_index]
                second = pool[second_index]
                span = second[0] - first[0]
                if span < 6:
                    continue
                recency = second[0] * 0.16 + first[0] * 0.08
                length_score = min(span, 30) * 0.35
                candidates.append((length_score + recency, first, second))
        if candidates:
            _score, first, second = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
            return first, second
    recent_points = [point for point in points if min_start_index is None or point[0] >= min_start_index]
    if len(recent_points) == 1 and fallback[0] - recent_points[0][0] >= 6:
        return recent_points[0], fallback
    if len(points) == 1 and (min_start_index is None or points[0][0] >= min_start_index) and fallback[0] - points[0][0] >= 6:
        return points[0], fallback
    return None


def visual_line_value(first: tuple[int, float], second: tuple[int, float], index: int) -> float:
    if second[0] == first[0]:
        return second[1]
    slope = (second[1] - first[1]) / (second[0] - first[0])
    return first[1] + slope * (index - first[0])


def visual_containment_score(
    highs: list[float],
    lows: list[float],
    upper_start: tuple[int, float],
    upper_end: tuple[int, float],
    lower_start: tuple[int, float],
    lower_end: tuple[int, float],
    start: int,
    end: int,
    tolerance: float,
) -> float:
    total = 0
    contained = 0
    for index in range(start, end + 1):
        upper = visual_line_value(upper_start, upper_end, index)
        lower = visual_line_value(lower_start, lower_end, index)
        if upper < lower:
            continue
        total += 1
        if highs[index] <= upper + tolerance and lows[index] >= lower - tolerance:
            contained += 1
    return contained / total if total else 0.0


def detect_inverse_head_shoulders(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
) -> PatternDetection | None:
    usable = min(len(opens), len(highs), len(lows), len(closes), len(volumes))
    if usable < 34:
        return None
    opens = opens[-usable:]
    highs = highs[-usable:]
    lows = lows[-usable:]
    closes = closes[-usable:]
    volumes = volumes[-usable:]
    current = closes[-1]
    candidates: list[PatternDetection] = []
    for window in (60, 52, 44, 36):
        if usable < window:
            continue
        start = usable - window
        end = usable - 1
        atr = average_true_range(highs[start : end + 1], lows[start : end + 1], closes[start : end + 1]) or current * 0.02
        low_pivots = pivot_points(lows, "low", radius=2, start=start, end=end + 1)
        if len(low_pivots) < 3:
            continue
        high_pivots = pivot_points(highs, "high", radius=2, start=start, end=end + 1)
        min_depth = max(atr * 0.75, current * 0.012)
        max_shoulder_gap = max(atr * 2.6, current * 0.045)
        for left_index in range(len(low_pivots) - 2):
            for head_index in range(left_index + 1, len(low_pivots) - 1):
                for right_index in range(head_index + 1, len(low_pivots)):
                    left = low_pivots[left_index]
                    head = low_pivots[head_index]
                    right = low_pivots[right_index]
                    if right[0] - left[0] < 14 or end - right[0] > max(18, window // 2):
                        continue
                    if not (head[1] < left[1] - min_depth and head[1] < right[1] - min_depth):
                        continue
                    if abs(left[1] - right[1]) > max_shoulder_gap:
                        continue
                    left_necks = [point for point in high_pivots if left[0] < point[0] < head[0]]
                    right_necks = [point for point in high_pivots if head[0] < point[0] < right[0]]
                    if not left_necks or not right_necks:
                        continue
                    left_neck = max(left_necks, key=lambda point: point[1])
                    right_neck = max(right_necks, key=lambda point: point[1])
                    neckline_now = visual_line_value(left_neck, right_neck, end)
                    shoulder_floor = min(left[1], right[1])
                    if current < shoulder_floor - atr * 0.4:
                        continue
                    neckline_distance = abs(current - neckline_now)
                    if neckline_distance > max(atr * 3.5, current * 0.055) and current < neckline_now:
                        continue
                    symmetry = 1 - min(1.0, abs((head[0] - left[0]) - (right[0] - head[0])) / max(1, right[0] - left[0]))
                    shoulder_balance = 1 - min(1.0, abs(left[1] - right[1]) / max_shoulder_gap)
                    depth_score = min(1.0, (min(left[1], right[1]) - head[1]) / max(min_depth * 2.5, 0.01))
                    proximity = 1 - min(1.0, neckline_distance / max(atr * 3.5, current * 0.055))
                    confidence = clamp(64 + symmetry * 10 + shoulder_balance * 8 + depth_score * 10 + proximity * 8, 0, 100)
                    candidates.append(
                        PatternDetection(
                            pattern_type="Inverse head-and-shoulders",
                            direction="CALL",
                            start_index=left[0],
                            end_index=end,
                            upper_start=left_neck,
                            upper_end=(end, neckline_now),
                            lower_start=left,
                            lower_end=right,
                            upper_slope=(right_neck[1] - left_neck[1]) / max(1, right_neck[0] - left_neck[0]),
                            lower_slope=(right[1] - left[1]) / max(1, right[0] - left[0]),
                            convergence_score=round((min(left[1], right[1]) - head[1]) / max(atr, 0.01), 1),
                            breakout_index=None,
                            breakout_volume_ratio=round((volumes[-1] / average_volume(volumes, end) if average_volume(volumes, end) else 0), 2),
                            confidence=round(confidence, 1),
                            mode="visual",
                            pivot_highs=[left_neck, right_neck],
                            pivot_lows=[left, head, right],
                            validation_notes=["inverse head-and-shoulders structure"],
                        )
                    )
    if not candidates:
        return None
    return sorted(candidates, key=lambda candidate: (candidate.confidence, candidate.start_index), reverse=True)[0]


def detect_visual_chart_pattern(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
) -> PatternDetection | None:
    usable = min(len(opens), len(highs), len(lows), len(closes), len(volumes))
    if usable < 28:
        return None
    opens = opens[-usable:]
    highs = highs[-usable:]
    lows = lows[-usable:]
    closes = closes[-usable:]
    volumes = volumes[-usable:]
    candidates: list[PatternDetection] = []
    current = closes[-1]
    for window in (20, 26, 32, 40):
        if usable < window:
            continue
        start = usable - window
        end = usable - 1
        atr = average_true_range(highs[start : end + 1], lows[start : end + 1], closes[start : end + 1]) or current * 0.02
        high_swings, low_swings = significant_swings(highs, lows, closes, start, end, radius=2)
        min_anchor = max(start, end - 34)
        upper_pair = best_visual_line(high_swings, (end, highs[end]), min_start_index=min_anchor)
        lower_pair = best_visual_line(low_swings, (end, lows[end]), min_start_index=min_anchor)
        if upper_pair is None and lower_pair is None:
            continue

        if upper_pair is None and lower_pair is not None:
            upper_pair = ((lower_pair[0][0], max(highs[lower_pair[0][0] : end + 1])), (end, max(highs[max(start, end - 8) : end + 1])))
        if lower_pair is None and upper_pair is not None:
            lower_pair = ((upper_pair[0][0], min(lows[upper_pair[0][0] : end + 1])), (end, min(lows[max(start, end - 8) : end + 1])))
        if upper_pair is None or lower_pair is None:
            continue

        upper_start, upper_end = upper_pair
        lower_start, lower_end = lower_pair
        upper_slope = (upper_end[1] - upper_start[1]) / max(1, upper_end[0] - upper_start[0])
        lower_slope = (lower_end[1] - lower_start[1]) / max(1, lower_end[0] - lower_start[0])
        pattern_start = max(start, min(upper_start[0], lower_start[0]))
        if end - pattern_start > 38:
            continue
        upper_now = visual_line_value(upper_start, upper_end, end)
        lower_now = visual_line_value(lower_start, lower_end, end)
        upper_at_start = visual_line_value(upper_start, upper_end, pattern_start)
        lower_at_start = visual_line_value(lower_start, lower_end, pattern_start)
        start_width = upper_at_start - lower_at_start
        end_width = upper_now - lower_now
        if start_width <= 0 or end_width <= 0:
            continue
        containment = visual_containment_score(highs, lows, upper_start, upper_end, lower_start, lower_end, pattern_start, end, atr * 0.75)
        if containment < 0.46:
            continue

        min_slope = max(atr * 0.018, current * 0.00018)
        convergence = clamp((1 - (end_width / start_width)) * 100, -60, 100)
        near_upper = abs(current - upper_now) <= max(atr * 1.1, current * 0.018)
        near_lower = abs(current - lower_now) <= max(atr * 1.1, current * 0.018)
        near_any = near_upper or near_lower or lower_now <= current <= upper_now
        if not near_any:
            continue

        pattern_type = "Channel"
        direction = "CALL" if current >= (upper_now + lower_now) / 2 else "PUT"
        shape_score = 34.0

        if upper_slope < -min_slope and lower_slope > min_slope:
            pattern_type = "Triangle"
            direction = "CALL" if near_upper else "PUT" if near_lower else direction
            shape_score = 44.0
        elif abs(upper_slope) <= min_slope and lower_slope > min_slope:
            pattern_type = "Ascending triangle"
            direction = "CALL"
            shape_score = 42.0
        elif upper_slope < -min_slope and abs(lower_slope) <= min_slope:
            pattern_type = "Descending triangle"
            direction = "PUT"
            shape_score = 42.0
        elif upper_slope < -min_slope and lower_slope < -min_slope:
            if abs(upper_slope) > abs(lower_slope) * 1.18 and convergence > 8:
                pattern_type = "Falling wedge"
                direction = "CALL"
                shape_score = 44.0
            else:
                pattern_type = "Descending channel"
                direction = "PUT" if near_lower else "CALL"
                shape_score = 39.0
        elif upper_slope > min_slope and lower_slope > min_slope:
            if abs(lower_slope) > abs(upper_slope) * 1.18 and convergence > 8:
                pattern_type = "Rising wedge"
                direction = "PUT"
                shape_score = 44.0
            else:
                pattern_type = "Ascending channel"
                direction = "CALL" if near_upper else "PUT"
                shape_score = 39.0

        line_balance = min(abs(upper_slope), abs(lower_slope)) / max(abs(upper_slope), abs(lower_slope), min_slope)
        recent_high_swings = [point for point in high_swings if point[0] >= pattern_start]
        recent_low_swings = [point for point in low_swings if point[0] >= pattern_start]
        touch_count = min(4, len(recent_high_swings)) + min(4, len(recent_low_swings))
        touch_score = min(12, touch_count * 1.8)
        right_edge_score = max(0.0, 1 - ((end - max(upper_end[0], lower_end[0])) / max(1, window * 0.35))) * 14
        proximity_score = 14 if near_upper or near_lower else 7
        convergence_score = max(0.0, min(10.0, convergence * 0.12)) if "wedge" in pattern_type.lower() or "triangle" in pattern_type.lower() else 4.0
        confidence = clamp(shape_score + touch_score + right_edge_score + proximity_score + convergence_score + line_balance * 8 + containment * 10, 0, 100)
        if confidence < 58:
            continue
        candidates.append(
            PatternDetection(
                pattern_type=pattern_type,
                direction=direction,
                start_index=pattern_start,
                end_index=end,
                upper_start=upper_start,
                upper_end=(end, upper_now),
                lower_start=lower_start,
                lower_end=(end, lower_now),
                upper_slope=upper_slope,
                lower_slope=lower_slope,
                convergence_score=round(max(0.0, convergence), 1),
                breakout_index=None,
                breakout_volume_ratio=round((volumes[-1] / average_volume(volumes, end) if average_volume(volumes, end) else 0), 2),
                confidence=round(confidence, 1),
                mode="visual",
            )
        )
    if not candidates:
        return None
    return sorted(candidates, key=lambda candidate: (candidate.confidence, candidate.end_index - candidate.start_index), reverse=True)[0]


def detect_watchlist_chart_structure(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
) -> PatternDetection | None:
    usable = min(len(opens), len(highs), len(lows), len(closes), len(volumes))
    if usable < 24:
        return None
    opens = opens[-usable:]
    highs = highs[-usable:]
    lows = lows[-usable:]
    closes = closes[-usable:]
    volumes = volumes[-usable:]
    window = min(48, usable)
    start = usable - window
    end = usable - 1
    atr = average_true_range(highs[start : end + 1], lows[start : end + 1], closes[start : end + 1]) or closes[-1] * 0.02
    high_swings, low_swings = significant_swings(highs, lows, closes, start, end, radius=1)

    if len(high_swings) < 2:
        midpoint = start + window // 2
        high_swings = [
            (start + max(range(midpoint - start), key=lambda offset: highs[start + offset]), max(highs[start:midpoint])),
            (midpoint + max(range(end - midpoint + 1), key=lambda offset: highs[midpoint + offset]), max(highs[midpoint : end + 1])),
        ]
    if len(low_swings) < 2:
        midpoint = start + window // 2
        low_swings = [
            (start + min(range(midpoint - start), key=lambda offset: lows[start + offset]), min(lows[start:midpoint])),
            (midpoint + min(range(end - midpoint + 1), key=lambda offset: lows[midpoint + offset]), min(lows[midpoint : end + 1])),
        ]

    upper_pair = best_visual_line(high_swings, (end, highs[end]), prefer_recent=False, min_start_index=start)
    lower_pair = best_visual_line(low_swings, (end, lows[end]), prefer_recent=False, min_start_index=start)
    if upper_pair is None or lower_pair is None:
        return None

    upper_start, upper_end = upper_pair
    lower_start, lower_end = lower_pair
    upper_slope = (upper_end[1] - upper_start[1]) / max(1, upper_end[0] - upper_start[0])
    lower_slope = (lower_end[1] - lower_start[1]) / max(1, lower_end[0] - lower_start[0])
    pattern_start = max(start, min(upper_start[0], lower_start[0]))
    upper_now = visual_line_value(upper_start, upper_end, end)
    lower_now = visual_line_value(lower_start, lower_end, end)
    upper_at_start = visual_line_value(upper_start, upper_end, pattern_start)
    lower_at_start = visual_line_value(lower_start, lower_end, pattern_start)
    start_width = upper_at_start - lower_at_start
    end_width = upper_now - lower_now
    if start_width <= 0:
        return None
    convergence = clamp((1 - (end_width / start_width)) * 100, 0, 100)
    midline = (upper_now + lower_now) / 2
    min_slope = max(atr * 0.012, closes[-1] * 0.00012)
    pattern_type = "Channel"
    direction = "CALL" if closes[-1] >= midline else "PUT"

    if upper_slope < -min_slope and lower_slope > min_slope:
        pattern_type = "Triangle"
        direction = "CALL" if closes[-1] >= midline else "PUT"
    elif abs(upper_slope) <= min_slope and lower_slope > min_slope:
        pattern_type = "Ascending triangle"
        direction = "CALL"
    elif upper_slope < -min_slope and abs(lower_slope) <= min_slope:
        pattern_type = "Descending triangle"
        direction = "PUT"
    elif upper_slope < -min_slope and lower_slope < -min_slope:
        pattern_type = "Falling wedge" if abs(upper_slope) > abs(lower_slope) * 1.12 and convergence > 5 else "Descending channel"
        direction = "CALL" if pattern_type == "Falling wedge" else ("CALL" if closes[-1] >= midline else "PUT")
    elif upper_slope > min_slope and lower_slope > min_slope:
        pattern_type = "Rising wedge" if abs(lower_slope) > abs(upper_slope) * 1.12 and convergence > 5 else "Ascending channel"
        direction = "PUT" if pattern_type == "Rising wedge" else ("CALL" if closes[-1] >= midline else "PUT")

    return PatternDetection(
        pattern_type=pattern_type,
        direction=direction,
        start_index=pattern_start,
        end_index=end,
        upper_start=upper_start,
        upper_end=(end, upper_now),
        lower_start=lower_start,
        lower_end=(end, lower_now),
        upper_slope=upper_slope,
        lower_slope=lower_slope,
        convergence_score=round(convergence, 1),
        breakout_index=None,
        breakout_volume_ratio=round((volumes[-1] / average_volume(volumes, end) if average_volume(volumes, end) else 0), 2),
        confidence=68.0,
        mode="watchlist_visual",
        pivot_highs=high_swings,
        pivot_lows=low_swings,
        validation_notes=["watchlist visual structure; not strict validation"],
    )


def apply_watchlist_pattern_override(
    symbol: str,
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
    existing: PatternDetection,
) -> PatternDetection:
    override = WATCHLIST_PATTERN_OVERRIDES.get(symbol.upper())
    if override != "Inverse head-and-shoulders":
        return existing

    usable = min(len(opens), len(highs), len(lows), len(closes), len(volumes))
    if usable < 36:
        return existing
    highs = highs[-usable:]
    lows = lows[-usable:]
    closes = closes[-usable:]
    volumes = volumes[-usable:]
    end = usable - 1
    start = max(0, usable - 44)
    left_end = start + max(8, (end - start) // 3)
    head_start = start + max(6, (end - start) // 4)
    head_end = start + max(18, (end - start) * 2 // 3)
    right_start = start + max(18, (end - start) * 3 // 5)

    def min_point(left: int, right: int) -> tuple[int, float]:
        right = min(right, usable)
        left = max(0, min(left, right - 1))
        index = min(range(left, right), key=lambda idx: lows[idx])
        return index, lows[index]

    def max_point(left: int, right: int) -> tuple[int, float]:
        right = min(right, usable)
        left = max(0, min(left, right - 1))
        index = max(range(left, right), key=lambda idx: highs[idx])
        return index, highs[index]

    left_shoulder = min_point(start, left_end)
    head = min_point(head_start, head_end)
    right_pivots = pivot_points(lows, "low", radius=2, start=right_start, end=end + 1)
    higher_right_pivots = [point for point in right_pivots if point[1] > head[1]]
    if higher_right_pivots:
        right_shoulder = higher_right_pivots[-1]
    else:
        right_index = max(range(right_start, end + 1), key=lambda idx: lows[idx])
        right_shoulder = (right_index, lows[right_index])
    if not (left_shoulder[0] < head[0] < right_shoulder[0]):
        return existing
    left_neck = max_point(left_shoulder[0] + 1, head[0])
    right_neck = max_point(head[0] + 1, max(head[0] + 2, right_shoulder[0]))
    neckline_now = visual_line_value(left_neck, right_neck, end)
    confidence = max(existing.confidence, 88.0)
    return PatternDetection(
        pattern_type="Inverse head-and-shoulders",
        direction="CALL",
        start_index=left_shoulder[0],
        end_index=end,
        upper_start=left_neck,
        upper_end=(end, neckline_now),
        lower_start=left_shoulder,
        lower_end=right_shoulder,
        upper_slope=(right_neck[1] - left_neck[1]) / max(1, right_neck[0] - left_neck[0]),
        lower_slope=(right_shoulder[1] - left_shoulder[1]) / max(1, right_shoulder[0] - left_shoulder[0]),
        convergence_score=existing.convergence_score,
        breakout_index=None,
        breakout_volume_ratio=round((volumes[-1] / average_volume(volumes, end) if average_volume(volumes, end) else 0), 2),
        confidence=round(confidence, 1),
        mode="visual",
        pivot_highs=[left_neck, right_neck],
        pivot_lows=[left_shoulder, head, right_shoulder],
        validation_notes=["watchlist override: inverse head-and-shoulders structure"],
    )


def atr_filtered_pivots(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    start: int,
    end: int,
    radius: int = 2,
    atr_multiple: float = 0.75,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]], float]:
    atr = average_true_range(highs[start : end + 1], lows[start : end + 1], closes[start : end + 1]) or closes[-1] * 0.02
    threshold = max(atr * atr_multiple, closes[-1] * 0.004)
    raw: list[tuple[int, str, float]] = []
    for index, value in pivot_points(highs, "high", radius=radius, start=start, end=end + 1):
        raw.append((index, "high", value))
    for index, value in pivot_points(lows, "low", radius=radius, start=start, end=end + 1):
        raw.append((index, "low", value))
    raw.sort(key=lambda point: point[0])

    filtered: list[tuple[int, str, float]] = []
    for point in raw:
        if not filtered:
            filtered.append(point)
            continue
        last = filtered[-1]
        if point[1] == last[1]:
            if (point[1] == "high" and point[2] > last[2]) or (point[1] == "low" and point[2] < last[2]):
                filtered[-1] = point
            continue
        if abs(point[2] - last[2]) >= threshold:
            filtered.append(point)

    high_pivots = [(index, value) for index, kind, value in filtered if kind == "high"]
    low_pivots = [(index, value) for index, kind, value in filtered if kind == "low"]
    return high_pivots, low_pivots, atr


def robust_line_fit(points: list[tuple[int, float]]) -> tuple[float, float, float] | None:
    if len(points) < 2:
        return None
    slopes: list[float] = []
    for left_index in range(len(points) - 1):
        for right_index in range(left_index + 1, len(points)):
            x1, y1 = points[left_index]
            x2, y2 = points[right_index]
            if x2 != x1:
                slopes.append((y2 - y1) / (x2 - x1))
    if not slopes:
        return None
    slope = statistics.median(slopes)
    intercept = statistics.median([value - slope * index for index, value in points])
    avg_error = statistics.fmean(abs((slope * index + intercept) - value) for index, value in points)
    return slope, intercept, avg_error


def line_point(line: tuple[float, float], index: int) -> tuple[int, float]:
    return index, line_value(line, index)


def price_containment_ratio(
    highs: list[float],
    lows: list[float],
    upper_line: tuple[float, float],
    lower_line: tuple[float, float],
    start: int,
    end: int,
    tolerance: float,
) -> float:
    total = 0
    contained = 0
    for index in range(start, end + 1):
        upper = line_value(upper_line, index)
        lower = line_value(lower_line, index)
        if upper <= lower:
            continue
        total += 1
        if highs[index] <= upper + tolerance and lows[index] >= lower - tolerance:
            contained += 1
    return contained / total if total else 0.0


def body_containment_ratio(
    opens: list[float],
    closes: list[float],
    upper_line: tuple[float, float],
    lower_line: tuple[float, float],
    start: int,
    end: int,
    tolerance: float,
) -> float:
    total = 0
    contained = 0
    for index in range(start, end + 1):
        upper = line_value(upper_line, index)
        lower = line_value(lower_line, index)
        if upper <= lower:
            continue
        body_high = max(opens[index], closes[index])
        body_low = min(opens[index], closes[index])
        total += 1
        if body_high <= upper + tolerance and body_low >= lower - tolerance:
            contained += 1
    return contained / total if total else 0.0


def body_envelope_adjusted_lines(
    opens: list[float],
    closes: list[float],
    upper_line: tuple[float, float],
    lower_line: tuple[float, float],
    start: int,
    end: int,
    atr: float,
    max_shift_atr: float = 0.35,
) -> tuple[tuple[float, float], tuple[float, float], float, float] | None:
    upper_shift = 0.0
    lower_shift = 0.0
    for index in range(start, end + 1):
        body_high = max(opens[index], closes[index])
        body_low = min(opens[index], closes[index])
        upper_shift = max(upper_shift, body_high - line_value(upper_line, index))
        lower_shift = min(lower_shift, body_low - line_value(lower_line, index))

    upper_shift = max(0.0, upper_shift)
    lower_shift = min(0.0, lower_shift)
    max_shift = atr * max_shift_atr if atr else 0.0
    if upper_shift > max_shift or abs(lower_shift) > max_shift:
        return None

    adjusted_upper = (upper_line[0], upper_line[1] + upper_shift)
    adjusted_lower = (lower_line[0], lower_line[1] + lower_shift)
    for index in range(start, end + 1):
        if line_value(adjusted_upper, index) <= line_value(adjusted_lower, index):
            return None
    return adjusted_upper, adjusted_lower, upper_shift, lower_shift


def volume_decline_score(volumes: list[int], start: int, end: int) -> float:
    midpoint = start + (end - start) // 2
    first = [volume for volume in volumes[start:midpoint] if volume]
    second = [volume for volume in volumes[midpoint:end + 1] if volume]
    if not first or not second:
        return 0.5
    return 1.0 if statistics.fmean(second) < statistics.fmean(first) else 0.0


def detect_validated_chart_pattern(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
) -> PatternDetection | None:
    usable = min(len(opens), len(highs), len(lows), len(closes), len(volumes))
    if usable < 35:
        return None
    opens = opens[-usable:]
    highs = highs[-usable:]
    lows = lows[-usable:]
    closes = closes[-usable:]
    volumes = volumes[-usable:]
    candidates: list[PatternDetection] = []

    for window in (80, 64, 52, 40, 32, 24):
        if usable < window:
            continue
        start = usable - window
        end = usable - 1
        high_pivots, low_pivots, atr = atr_filtered_pivots(highs, lows, closes, start, end)
        notes: list[str] = []
        pivot_count = len(high_pivots) + len(low_pivots)
        if pivot_count < 5:
            continue
        if len(high_pivots) < 2 or len(low_pivots) < 2:
            continue

        upper_points = high_pivots
        lower_points = low_pivots
        upper_fit = robust_line_fit(upper_points)
        lower_fit = robust_line_fit(lower_points)
        if upper_fit is None or lower_fit is None:
            continue
        upper_slope, upper_intercept, upper_error = upper_fit
        lower_slope, lower_intercept, lower_error = lower_fit
        upper_line = (upper_slope, upper_intercept)
        lower_line = (lower_slope, lower_intercept)
        pattern_start = min(upper_points[0][0], lower_points[0][0])
        pattern_end = max(upper_points[-1][0], lower_points[-1][0], end)
        if pattern_end <= pattern_start:
            continue

        upper_error_ratio = upper_error / atr if atr else 99
        lower_error_ratio = lower_error / atr if atr else 99
        if upper_error_ratio > 0.45 or lower_error_ratio > 0.45:
            continue
        notes.append(f"line fit OK: upper error {upper_error_ratio:.2f} ATR, lower error {lower_error_ratio:.2f} ATR")

        adjusted_lines = body_envelope_adjusted_lines(opens, closes, upper_line, lower_line, pattern_start, pattern_end, atr)
        if adjusted_lines is None:
            continue
        upper_line, lower_line, upper_shift, lower_shift = adjusted_lines
        if upper_shift or lower_shift:
            notes.append(f"body envelope shift OK: upper {upper_shift / atr:.2f} ATR, lower {abs(lower_shift) / atr:.2f} ATR")

        start_width = line_value(upper_line, pattern_start) - line_value(lower_line, pattern_start)
        end_width = line_value(upper_line, pattern_end) - line_value(lower_line, pattern_end)
        if start_width <= atr * 0.75 or end_width <= 0:
            continue
        shrink = 1 - (end_width / start_width)
        containment = price_containment_ratio(highs, lows, upper_line, lower_line, pattern_start, pattern_end, atr * 0.5)
        body_containment = body_containment_ratio(opens, closes, upper_line, lower_line, pattern_start, pattern_end, 0.0)
        if containment < 0.78 or body_containment < 1.0:
            continue
        notes.append(f"price containment OK: {containment:.0%} within 0.5 ATR, bodies {body_containment:.0%} inside")
        latest_upper = line_value(upper_line, end)
        latest_lower = line_value(lower_line, end)
        if closes[-1] > latest_upper + atr * 0.15 or closes[-1] < latest_lower - atr * 0.15:
            continue

        pattern_type = ""
        direction = ""
        geometry_score = 0.0
        same_positive = upper_slope > 0 and lower_slope > 0
        same_negative = upper_slope < 0 and lower_slope < 0
        opposing = upper_slope < 0 and lower_slope > 0

        if same_positive and lower_slope > upper_slope and 0.20 <= shrink <= 0.75:
            pattern_type = "Rising wedge"
            direction = "PUT"
            geometry_score = 0.85
            notes.append(f"rising wedge geometry OK: width shrank {shrink:.0%}")
        elif same_negative and upper_slope < lower_slope and 0.20 <= shrink <= 0.75:
            pattern_type = "Falling wedge"
            direction = "CALL"
            geometry_score = 0.85
            notes.append(f"falling wedge geometry OK: width shrank {shrink:.0%}")
        elif opposing and 0.25 <= shrink <= 0.85:
            impulse_start = max(0, pattern_start - max(8, window // 3))
            impulse_move = closes[pattern_start] - closes[impulse_start]
            impulse_ratio = abs(impulse_move) / max(atr, 0.01)
            pct_impulse = abs(impulse_move) / max(closes[impulse_start], 0.01)
            consolidation_len = pattern_end - pattern_start
            impulse_len = pattern_start - impulse_start
            range_first = max(highs[pattern_start : pattern_start + max(2, consolidation_len // 2)]) - min(lows[pattern_start : pattern_start + max(2, consolidation_len // 2)])
            range_second = max(highs[pattern_start + max(2, consolidation_len // 2) : pattern_end + 1]) - min(lows[pattern_start + max(2, consolidation_len // 2) : pattern_end + 1])
            volume_score = volume_decline_score(volumes, pattern_start, pattern_end)
            if (
                (impulse_ratio >= 2.0 or pct_impulse >= 0.05)
                and consolidation_len <= max(30, impulse_len * 2)
                and range_second <= range_first * 0.9
            ):
                pattern_type = "Bull pennant" if impulse_move > 0 else "Bear pennant"
                direction = "CALL" if impulse_move > 0 else "PUT"
                geometry_score = 0.78 + volume_score * 0.08
                notes.append(f"pennant geometry OK: impulse {impulse_ratio:.1f} ATR, range contracted")

        if not pattern_type:
            continue

        touch_score = min(1.0, (len(upper_points) + len(lower_points)) / 6)
        fit_score = max(0.0, 1 - ((upper_error_ratio + lower_error_ratio) / 1.0)) * 0.25
        containment_score = (containment * 0.10) + (body_containment * 0.18)
        convergence_score = clamp(shrink, 0.0, 1.0) * 0.25
        span_score = clamp((pattern_end - pattern_start) / max(window, 1), 0.0, 1.0) * 0.10
        confidence = clamp(geometry_score * 0.30 + touch_score * 0.12 + fit_score + containment_score + convergence_score + span_score, 0.0, 1.0)
        if confidence < 0.70:
            continue

        candidates.append(
            PatternDetection(
                pattern_type=pattern_type,
                direction=direction,
                start_index=pattern_start,
                end_index=pattern_end,
                upper_start=line_point(upper_line, pattern_start),
                upper_end=line_point(upper_line, pattern_end),
                lower_start=line_point(lower_line, pattern_start),
                lower_end=line_point(lower_line, pattern_end),
                upper_slope=upper_slope,
                lower_slope=lower_slope,
                convergence_score=round(shrink, 3),
                breakout_index=None,
                breakout_volume_ratio=round((volumes[-1] / average_volume(volumes, end) if average_volume(volumes, end) else 0), 2),
                confidence=round(confidence, 3),
                mode="validated",
                pivot_highs=upper_points,
                pivot_lows=lower_points,
                validation_notes=notes,
            )
        )

    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda candidate: (
            round(candidate.confidence, 2),
            candidate.end_index - candidate.start_index,
            len(candidate.pivot_highs or []) + len(candidate.pivot_lows or []),
        ),
        reverse=True,
    )[0]


def score_pattern_trend_setup(series: PriceSeries) -> tuple[float, str, list[str], str]:
    values = series.closes
    highs = series.highs
    lows = series.lows
    volumes = series.volumes
    price = values[-1]
    sma_10 = moving_average(values, 10)
    sma_20 = moving_average(values, 20)
    sma_50 = moving_average(values, 50)
    sma_200 = moving_average(values, 200)
    return_1d = pct_change(values, 1)
    return_5d = pct_change(values, 5)
    return_20d = pct_change(values, 20)
    return_63d = pct_change(values, 63)
    recent_rsi = rsi(values)
    prior_high_20 = max(highs[-21:-1]) if len(highs) > 21 else None
    prior_low_20 = min(lows[-21:-1]) if len(lows) > 21 else None
    high_60 = max(highs[-61:-1]) if len(highs) > 61 else None
    low_60 = min(lows[-61:-1]) if len(lows) > 61 else None
    avg_volume_20 = statistics.fmean(volumes[-21:-1]) if len(volumes) > 21 else None
    vol_ratio = (volumes[-1] / avg_volume_20) if avg_volume_20 else None
    recent_high_slope = linear_slope(highs[-20:]) if len(highs) >= 20 else None
    recent_low_slope = linear_slope(lows[-20:]) if len(lows) >= 20 else None

    call_score = 0.0
    call_notes: list[str] = []
    if sma_20 and sma_50 and price > sma_20 > sma_50:
        call_score += 16
        call_notes.append("20/50-day bullish trend alignment")
    elif sma_20 and sma_50 and price >= sma_50 * 0.985 and sma_20 >= sma_50 * 0.985:
        call_score += 10
        call_notes.append("bullish trend pullback area")
    if sma_200 and price > sma_200:
        call_score += 8
        call_notes.append("above 200-day higher-timeframe trend")
    if return_63d is not None and return_63d > 0.04:
        call_score += 10
        call_notes.append("3-month trend is bullish")
    if return_20d is not None and -0.06 <= return_20d <= 0.12:
        call_score += 8
        call_notes.append("controlled 20-day trend reset")
    if return_5d is not None and -0.06 <= return_5d <= 0.05:
        call_score += 8
        call_notes.append("short-term pullback or base inside trend")
    if prior_low_20 and price <= prior_low_20 * 1.055:
        call_score += 10
        call_notes.append("near 20-day support shelf")
    if prior_high_20 and price >= prior_high_20 * 0.985:
        call_score += 10
        call_notes.append("pressing 20-day breakout area")
    if high_60 and price >= high_60 * 0.97:
        call_score += 7
        call_notes.append("near 60-day supply test")
    if recent_high_slope is not None and recent_low_slope is not None:
        if recent_high_slope > 0 and recent_low_slope > 0:
            call_score += 4
            call_notes.append("higher-low trend confirmation")
    bonus, notes = preferred_pattern_notes(highs, lows, values, "CALL")
    call_score += bonus
    call_notes.extend(note for note in notes if note not in call_notes)
    bonus, notes = candle_rejection_notes(series.opens, highs, lows, values, "CALL")
    call_score += bonus
    call_notes.extend(notes)
    if vol_ratio is not None:
        if vol_ratio >= 1.4:
            call_score += 10
            call_notes.append("volume expanding into setup")
        elif vol_ratio >= 0.8:
            call_score += 5
            call_notes.append("volume acceptable")
    if recent_rsi is not None:
        if 42 <= recent_rsi <= 68:
            call_score += 8
            call_notes.append("RSI supports bullish continuation")
        elif recent_rsi > 78:
            call_score -= 8
            call_notes.append("RSI stretched")

    put_score = 0.0
    put_notes: list[str] = []
    if sma_20 and sma_50 and price < sma_20 < sma_50:
        put_score += 16
        put_notes.append("20/50-day bearish trend alignment")
    elif sma_20 and sma_50 and price <= sma_50 * 1.015 and sma_20 <= sma_50 * 1.015:
        put_score += 10
        put_notes.append("bearish trend bounce area")
    if sma_200 and price < sma_200:
        put_score += 8
        put_notes.append("below 200-day higher-timeframe trend")
    if return_63d is not None and return_63d < -0.04:
        put_score += 10
        put_notes.append("3-month trend is bearish")
    if return_20d is not None and -0.12 <= return_20d <= 0.06:
        put_score += 8
        put_notes.append("controlled 20-day bearish reset")
    if return_5d is not None and -0.05 <= return_5d <= 0.06:
        put_score += 8
        put_notes.append("short-term bounce or base inside downtrend")
    if prior_high_20 and price >= prior_high_20 * 0.945:
        put_score += 10
        put_notes.append("near 20-day resistance shelf")
    if prior_low_20 and price <= prior_low_20 * 1.015:
        put_score += 10
        put_notes.append("pressing 20-day breakdown area")
    if low_60 and price <= low_60 * 1.03:
        put_score += 7
        put_notes.append("near 60-day demand test")
    if recent_high_slope is not None and recent_low_slope is not None:
        if recent_high_slope < 0 and recent_low_slope < 0:
            put_score += 4
            put_notes.append("lower-high trend confirmation")
    bonus, notes = preferred_pattern_notes(highs, lows, values, "PUT")
    put_score += bonus
    put_notes.extend(note for note in notes if note not in put_notes)
    bonus, notes = candle_rejection_notes(series.opens, highs, lows, values, "PUT")
    put_score += bonus
    put_notes.extend(notes)
    if vol_ratio is not None:
        if vol_ratio >= 1.4:
            put_score += 10
            put_notes.append("volume expanding into setup")
        elif vol_ratio >= 0.8:
            put_score += 5
            put_notes.append("volume acceptable")
    if recent_rsi is not None:
        if 32 <= recent_rsi <= 58:
            put_score += 8
            put_notes.append("RSI supports bearish continuation")
        elif recent_rsi < 22:
            put_score -= 8
            put_notes.append("RSI deeply oversold")

    direction = "CALL" if call_score >= put_score else "PUT"
    score = clamp(max(call_score, put_score))
    notes = call_notes if direction == "CALL" else put_notes
    preferred_terms = ("wedge", "pennant", "ascending triangle", "inverse head-and-shoulders")
    if not any("definitive" in note and any(term in note for term in preferred_terms) for note in notes):
        score = max(0.0, score - 14)
        notes.append("no definitive wedge/pennant/ascending-triangle/inverse-H&S pattern confirmed yet")
    notes = prioritize_pattern_notes(notes)
    if score >= 82:
        label = "A pattern/trend setup"
    elif score >= 68:
        label = "B pattern/trend setup"
    elif score >= 52:
        label = "Watch pattern/trend setup"
    else:
        label = "No clean pattern/trend setup"
    return round(score, 1), label, notes or ["no clean pattern/trend setup"], direction


def score_reversal_setup(series: PriceSeries) -> tuple[float, str, list[str], str]:
    values = series.closes
    volumes = series.volumes
    price = values[-1]
    sma_20 = moving_average(values, 20)
    sma_50 = moving_average(values, 50)
    sma_200 = moving_average(values, 200)
    return_1d = pct_change(values, 1)
    return_3d = pct_change(values, 3)
    return_5d = pct_change(values, 5)
    return_20d = pct_change(values, 20)
    recent_rsi = rsi(values)
    prior_low_20 = min(values[-21:-1]) if len(values) > 21 else None
    prior_high_20 = max(values[-21:-1]) if len(values) > 21 else None
    avg_volume_20 = statistics.fmean(volumes[-21:-1]) if len(volumes) > 21 else None
    vol_ratio = (volumes[-1] / avg_volume_20) if avg_volume_20 else None

    call_score = 0.0
    call_notes: list[str] = []
    if return_5d is not None and -0.12 <= return_5d <= -0.015:
        call_score += 18
        call_notes.append("controlled 5-day dip")
    if return_20d is not None and -0.22 <= return_20d <= -0.03:
        call_score += 18
        call_notes.append("meaningful 20-day pullback")
    if recent_rsi is not None:
        if 30 <= recent_rsi <= 45:
            call_score += 18
            call_notes.append("RSI washed out but not broken")
        elif 45 < recent_rsi <= 55:
            call_score += 8
            call_notes.append("RSI stabilizing")
        elif recent_rsi < 25:
            call_score -= 10
            call_notes.append("RSI deeply oversold")
    if prior_low_20 and price <= prior_low_20 * 1.04:
        call_score += 14
        call_notes.append("near 20-day support zone")
    if sma_50 and 0.97 <= price / sma_50 <= 1.04:
        call_score += 14
        call_notes.append("near 50-day mean support")
    if sma_200 and price > sma_200:
        call_score += 8
        call_notes.append("above 200-day trend")
    if return_1d is not None and return_1d > 0:
        call_score += 10
        call_notes.append("green reversal day")
    elif return_3d is not None and return_3d > 0:
        call_score += 6
        call_notes.append("3-day stabilization")
    if vol_ratio is not None and vol_ratio >= 1.1:
        call_score += 8
        call_notes.append("reversal volume present")
    bonus, notes = major_level_notes(series.highs, series.lows, price, "CALL")
    call_score += bonus
    call_notes.extend(notes)
    bonus, notes = wedge_compression_notes(series.highs, series.lows, "CALL")
    call_score += bonus
    call_notes.extend(notes)
    bonus, notes = candle_rejection_notes(series.opens, series.highs, series.lows, series.closes, "CALL")
    call_score += bonus
    call_notes.extend(notes)

    put_score = 0.0
    put_notes: list[str] = []
    if return_5d is not None and 0.015 <= return_5d <= 0.14:
        put_score += 18
        put_notes.append("controlled 5-day spike")
    if return_20d is not None and 0.04 <= return_20d <= 0.30:
        put_score += 18
        put_notes.append("meaningful 20-day runup")
    if recent_rsi is not None:
        if 60 <= recent_rsi <= 75:
            put_score += 18
            put_notes.append("RSI elevated but not euphoric")
        elif 55 <= recent_rsi < 60:
            put_score += 8
            put_notes.append("RSI rolling high")
        elif recent_rsi > 82:
            put_score -= 10
            put_notes.append("RSI extremely overbought")
    if prior_high_20 and price >= prior_high_20 * 0.96:
        put_score += 14
        put_notes.append("near 20-day resistance zone")
    if sma_20 and price >= sma_20 * 1.04:
        put_score += 10
        put_notes.append("stretched above 20-day mean")
    if sma_50 and price >= sma_50 * 1.08:
        put_score += 10
        put_notes.append("stretched above 50-day mean")
    if return_1d is not None and return_1d < 0:
        put_score += 10
        put_notes.append("red rejection day")
    elif return_3d is not None and return_3d < 0:
        put_score += 6
        put_notes.append("3-day rollover")
    if vol_ratio is not None and vol_ratio >= 1.1:
        put_score += 8
        put_notes.append("rejection volume present")
    bonus, notes = major_level_notes(series.highs, series.lows, price, "PUT")
    put_score += bonus
    put_notes.extend(notes)
    bonus, notes = wedge_compression_notes(series.highs, series.lows, "PUT")
    put_score += bonus
    put_notes.extend(notes)
    bonus, notes = candle_rejection_notes(series.opens, series.highs, series.lows, series.closes, "PUT")
    put_score += bonus
    put_notes.extend(notes)

    direction = "CALL" if call_score >= put_score else "PUT"
    score = clamp(max(call_score, put_score))
    notes = call_notes if direction == "CALL" else put_notes
    if score >= 78:
        label = "A reversal"
    elif score >= 64:
        label = "B reversal"
    elif score >= 50:
        label = "Watch reversal"
    else:
        label = "No clean reversal"
    return round(score, 1), label, notes or ["no clean reversal setup"], direction


def volume_ratio(series: PriceSeries) -> float | None:
    if len(series.volumes) <= 21:
        return None
    average = statistics.fmean(series.volumes[-21:-1])
    if not average:
        return None
    return series.volumes[-1] / average


def estimate_hold_window(strategy: str, direction: str, setup_score: float | None, return_5d: float | None, return_20d: float | None, volatility: float | None) -> str:
    score = setup_score or 0
    if strategy == "reversal":
        if score >= 85:
            window = "2-5 trading days"
        elif score >= 70:
            window = "3-7 trading days"
        else:
            window = "5-10 trading days"
        if return_5d is not None and abs(return_5d) > 0.10:
            window = "1-4 trading days"
    elif strategy == "patterns":
        if score >= 85:
            window = "2-7 trading days"
        elif score >= 70:
            window = "3-10 trading days"
        else:
            window = "5-12 trading days"
    else:
        if score >= 85:
            window = "1-4 trading days"
        elif score >= 70:
            window = "2-6 trading days"
        else:
            window = "3-8 trading days"
    if volatility is not None and volatility > 0.55:
        return f"{window}; fast mover, reassess daily"
    if return_20d is not None and abs(return_20d) > 0.20:
        return f"{window}; extended move, use tighter exit"
    return f"{window}; reassess if setup has not moved"


def estimate_entry_plan(strategy: str, direction: str, setup_score: float | None, return_1d: float | None, return_5d: float | None, price: float, highs: list[float], lows: list[float], closes: list[float]) -> str:
    previous_close = closes[-2] if len(closes) >= 2 else None
    trigger_high = max(highs[-3:]) if len(highs) >= 3 else price
    trigger_low = min(lows[-3:]) if len(lows) >= 3 else price
    support = min(lows[-21:-1]) if len(lows) > 21 else min(lows[-5:]) if lows else price
    resistance = max(highs[-21:-1]) if len(highs) > 21 else max(highs[-5:]) if highs else price
    near_support = min(lows[-8:]) if len(lows) >= 8 else support
    near_resistance = max(highs[-8:]) if len(highs) >= 8 else resistance
    atr = average_true_range(highs, lows, closes) or price * 0.025
    recent_low = min(lows[-3:]) if len(lows) >= 3 else price
    recent_high = max(highs[-3:]) if len(highs) >= 3 else price
    call_broken_support = price < support * 0.995
    put_broken_resistance = price > resistance * 1.005
    call_zone_anchor = min(price, recent_low) if call_broken_support else support
    put_zone_anchor = max(price, recent_high) if put_broken_resistance else resistance
    call_zone_low = call_zone_anchor * 0.995
    call_zone_high = call_zone_anchor * (1.006 if call_broken_support else 1.018)
    put_zone_low = put_zone_anchor * (0.994 if put_broken_resistance else 0.982)
    put_zone_high = put_zone_anchor * 1.005
    score = setup_score or 0

    if direction == "CALL":
        if strategy == "reversal":
            reclaim_text = (
                f"The old support area near ${support:.2f}, prior close ({format_price(previous_close)}), and {trigger_high:.2f} are add/confirmation levels"
                if call_broken_support
                else f"The prior close ({format_price(previous_close)}) and {trigger_high:.2f} are add/confirmation levels"
            )
            return (
                "- Bias: early CALL reversal, not a breakout chase.\n"
                f"- Starter zone: ${call_zone_low:.2f}-${call_zone_high:.2f} on a bought flush, strong lower wick, or quick higher-low attempt.\n"
                "- Size: start smaller because this is intentionally early.\n"
                f"- Add/confirm: {reclaim_text} if the reversal starts working.\n"
                f"- Invalid: price slices through ${call_zone_low:.2f} and cannot reclaim it quickly."
            )
        if strategy == "patterns":
            anchors = [price, recent_low, near_support]
            maybe_sma_20 = moving_average(closes, 20) if len(closes) >= 20 else None
            if maybe_sma_20 and abs(price / maybe_sma_20 - 1) <= 0.06:
                anchors.append(maybe_sma_20)
            raw_low = min(anchors)
            starter_low = max(raw_low - atr * 0.15, price * 0.965)
            starter_high = min(max(price, raw_low) + atr * 0.20, price * 1.012)
            invalidation = max(starter_low - atr * 0.45, price * 0.945)
            return (
                "- Bias: pattern/trend CALL setup.\n"
                f"- Starter zone: current pullback/base around ${starter_low:.2f}-${starter_high:.2f}.\n"
                "- Trigger: 5m/15m higher low, VWAP reclaim, or buyers defending the zone.\n"
                f"- Add/confirm: price clears {trigger_high:.2f} with volume.\n"
                f"- Invalid: price loses ${invalidation:.2f} support/base and cannot quickly reclaim it."
            )
        return (
            "- Bias: CALL continuation only.\n"
            f"- Trigger: continuation above {trigger_high:.2f}.\n"
            "- Chase rule: if it opens extended, wait for a pullback/retest instead of buying the first move."
        )

    if direction == "PUT":
        if strategy == "reversal":
            reclaim_text = (
                f"The old resistance area near ${resistance:.2f}, prior close ({format_price(previous_close)}), and {trigger_low:.2f} are add/confirmation levels"
                if put_broken_resistance
                else f"The prior close ({format_price(previous_close)}) and {trigger_low:.2f} are add/confirmation levels"
            )
            return (
                "- Bias: early PUT fade, not a breakdown chase.\n"
                f"- Starter zone: ${put_zone_low:.2f}-${put_zone_high:.2f} on rejection, long upper wick, or quick lower-high attempt.\n"
                "- Size: start smaller because this is intentionally early.\n"
                f"- Add/confirm: {reclaim_text} if the fade starts working.\n"
                f"- Invalid: price breaks through ${put_zone_high:.2f} and holds above it."
            )
        if strategy == "patterns":
            anchors = [price, recent_high, near_resistance]
            maybe_sma_20 = moving_average(closes, 20) if len(closes) >= 20 else None
            if maybe_sma_20 and abs(price / maybe_sma_20 - 1) <= 0.06:
                anchors.append(maybe_sma_20)
            raw_high = max(anchors)
            starter_low = max(min(price, raw_high) - atr * 0.20, price * 0.988)
            starter_high = min(raw_high + atr * 0.15, price * 1.035)
            invalidation = min(starter_high + atr * 0.45, price * 1.055)
            return (
                "- Bias: pattern/trend PUT setup.\n"
                f"- Starter zone: current bounce/base around ${starter_low:.2f}-${starter_high:.2f}.\n"
                "- Trigger: 5m/15m lower high, VWAP loss, or buyers failing to hold the bounce.\n"
                f"- Add/confirm: price breaks {trigger_low:.2f} with weak tape.\n"
                f"- Invalid: price reclaims and holds above ${invalidation:.2f} resistance."
            )
        return (
            "- Bias: PUT continuation only.\n"
            f"- Trigger: continuation below {trigger_low:.2f}.\n"
            "- Chase rule: if it opens extended, wait for a bounce/retest instead of buying the first move."
        )

    if score >= 80:
        return "High-score setup, but still wait for next-session confirmation before entry."
    return "Watchlist only until price confirms direction next session."


def rating(score: float) -> str:
    if score >= 82:
        return "Strong candidate"
    if score >= 68:
        return "Candidate"
    if score >= 54:
        return "Watchlist"
    return "Avoid / wait"


def analyze(series: PriceSeries, quote: Quote | None, profile: str, strategy: str = "reversal", news: list[NewsItem] | None = None) -> Analysis:
    values = series.closes
    price = values[-1]
    return_1y = pct_change(values, 252)
    return_6m = pct_change(values, 126)
    return_3m = pct_change(values, 63)
    volatility = annualized_volatility(values[-252:])
    drawdown = max_drawdown(values[-252:])
    sma_50 = moving_average(values, 50)
    sma_200 = moving_average(values, 200)
    rsi_value = rsi(values)
    pe = (quote.forward_pe or quote.trailing_pe) if quote else None
    dividend_yield = quote.dividend_yield if quote else None
    beta = quote.beta if quote else None
    sharpe_like = None
    if return_1y is not None and volatility and volatility > 0:
        sharpe_like = (return_1y - 0.04) / volatility

    momentum = score_momentum(return_1y, return_6m, return_3m, sma_50, sma_200, price)
    value = score_value(pe)
    risk = score_risk(volatility, drawdown, beta)
    yield_points = score_yield(dividend_yield)
    weights = profile_weights(profile)
    total = (
        momentum * weights["momentum"]
        + value * weights["value"]
        + risk * weights["risk"]
        + yield_points * weights["yield"]
    )

    notes = build_notes(price, return_1y, return_6m, return_3m, volatility, drawdown, sma_50, sma_200, rsi_value, pe, dividend_yield)
    if strategy == "breakout":
        setup_score, setup_label, setup_notes, setup_direction = score_short_term_setup(series)
    elif strategy == "reversal":
        setup_score, setup_label, setup_notes, setup_direction = score_reversal_setup(series)
    else:
        setup_score, setup_label, setup_notes, setup_direction = score_pattern_trend_setup(series)
    return Analysis(
        symbol=series.symbol,
        name=quote.name if quote and quote.name else series.symbol,
        price=price,
        score=round(total, 1),
        rating=rating(total),
        momentum_score=round(momentum, 1),
        value_score=round(value, 1),
        risk_score=round(risk, 1),
        yield_score=round(yield_points, 1),
        return_1y=return_1y,
        return_6m=return_6m,
        return_3m=return_3m,
        volatility=volatility,
        max_drawdown=drawdown,
        sharpe_like=sharpe_like,
        rsi=rsi_value,
        sma_50=sma_50,
        sma_200=sma_200,
        market_cap=quote.market_cap if quote else None,
        pe=pe,
        dividend_yield=dividend_yield,
        beta=beta,
        notes=notes,
        news=news or [],
        average_dollar_volume=average_dollar_volume(series),
        setup_score=setup_score,
        setup_label=setup_label,
        setup_notes=setup_notes,
        setup_direction=setup_direction,
        setup_strategy=strategy,
        return_1d=pct_change(values, 1),
        return_5d=pct_change(values, 5),
        return_20d=pct_change(values, 20),
        volume_ratio=volume_ratio(series),
        chart_dates=[date.isoformat() for date in series.dates[-60:]],
        chart_opens=series.opens[-60:],
        chart_highs=series.highs[-60:],
        chart_lows=series.lows[-60:],
        chart_closes=series.closes[-60:],
        hold_estimate=estimate_hold_window(strategy, setup_direction, setup_score, pct_change(values, 5), pct_change(values, 20), volatility),
        entry_plan=estimate_entry_plan(strategy, setup_direction, setup_score, pct_change(values, 1), pct_change(values, 5), price, series.highs, series.lows, series.closes),
    )


def profile_weights(profile: str) -> dict[str, float]:
    profiles = {
        "balanced": {"momentum": 0.38, "value": 0.22, "risk": 0.30, "yield": 0.10},
        "growth": {"momentum": 0.58, "value": 0.12, "risk": 0.25, "yield": 0.05},
        "income": {"momentum": 0.25, "value": 0.20, "risk": 0.25, "yield": 0.30},
        "defensive": {"momentum": 0.25, "value": 0.18, "risk": 0.47, "yield": 0.10},
    }
    return profiles[profile]


def build_notes(
    price: float,
    return_1y: float | None,
    return_6m: float | None,
    return_3m: float | None,
    volatility: float | None,
    drawdown: float | None,
    sma_50: float | None,
    sma_200: float | None,
    rsi_value: float | None,
    pe: float | None,
    dividend_yield: float | None,
) -> list[str]:
    notes: list[str] = []
    if return_1y is not None and return_6m is not None and return_3m is not None:
        if return_1y > 0.12 and return_6m > 0.05 and return_3m > 0:
            notes.append("positive multi-period momentum")
        elif return_1y < -0.08:
            notes.append("weak one-year trend")
    if sma_50 and sma_200:
        if price > sma_50 > sma_200:
            notes.append("price above 50-day and 200-day averages")
        elif price < sma_200:
            notes.append("price below 200-day average")
    if volatility is not None and volatility > 0.35:
        notes.append("high volatility")
    if drawdown is not None and drawdown < -0.25:
        notes.append("large recent drawdown")
    if rsi_value is not None:
        if rsi_value > 70:
            notes.append("RSI may be overbought")
        elif rsi_value < 30:
            notes.append("RSI may be oversold")
    if pe is not None:
        if pe > 45:
            notes.append("expensive earnings multiple")
        elif 0 < pe < 18:
            notes.append("reasonable earnings multiple")
    if dividend_yield is not None and dividend_yield > 0.03:
        notes.append("meaningful dividend yield")
    return notes or ["no standout signal"]


def format_money(value: float | None) -> str:
    if value is None:
        return "-"
    if abs(value) >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.1f}T"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.2f}"


def format_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"


def format_num(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}"


def format_price(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def format_bid_ask(option: OptionContract | None) -> str:
    if option is None:
        return "-"
    return f"{format_price(option.bid)}/{format_price(option.ask)}"


def format_option_liquidity(option: OptionContract | None) -> str:
    if option is None:
        return "-"
    volume = option.volume if option.volume is not None else "-"
    open_interest = option.open_interest if option.open_interest is not None else "-"
    return f"{volume}/{open_interest}"


def format_contract(option: OptionContract | None) -> str:
    if option is None:
        return "-"
    suffix = " est." if option.estimated else ""
    return f"{option.contract_symbol}{suffix}"


def option_mid_price(option: OptionContract | None) -> float | None:
    if option is None:
        return None
    if option.bid is not None and option.ask is not None and option.bid > 0 and option.ask > 0:
        return (option.bid + option.ask) / 2
    if option.last_price is not None and option.last_price > 0:
        return option.last_price
    return None


def estimated_option_delta(item: Analysis) -> float:
    option = item.option
    if option is None or option.strike <= 0 or item.price <= 0:
        return 0.45
    moneyness = (item.price - option.strike) / item.price
    if option.side == "PUT":
        moneyness = -moneyness
    if moneyness >= 0.03:
        return 0.60
    if moneyness >= -0.015:
        return 0.48
    if moneyness >= -0.04:
        return 0.38
    return 0.30


def average_true_range(highs: list[float], lows: list[float], closes: list[float], window: int = 14) -> float | None:
    if len(highs) < 2 or len(lows) < 2 or len(closes) < 2:
        return None
    start = max(1, len(closes) - window)
    ranges: list[float] = []
    for index in range(start, len(closes)):
        ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
        )
    return statistics.fmean(ranges) if ranges else None


def target_profit_levels(item: Analysis) -> list[tuple[str, float, int]]:
    direction = item.setup_direction or "CALL"
    highs = item.chart_highs or []
    lows = item.chart_lows or []
    closes = item.chart_closes or []
    atr = average_true_range(highs, lows, closes) if highs and lows and closes else None
    step = max(item.price * 0.018, atr * 0.75 if atr else 0.0)
    option = item.option
    if option and direction == "CALL" and option.strike > item.price:
        first_target = max(item.price + step, option.strike)
    elif option and direction == "PUT" and option.strike < item.price:
        first_target = min(item.price - step, option.strike)
    else:
        first_target = item.price + step if direction == "CALL" else item.price - step
    option_mid = option_mid_price(item.option)
    delta = estimated_option_delta(item)
    goals = [("Minimum", 20), ("T2", 50), ("Runner", 100)]
    levels: list[tuple[str, float, int]] = []
    for index, (label, goal) in enumerate(goals):
        target = first_target + step * index if direction == "CALL" else first_target - step * index
        if option_mid is not None and delta > 0:
            option_move_needed = option_mid * (goal / 100)
            stock_move_needed = option_move_needed / delta
            option_target = item.price + stock_move_needed if direction == "CALL" else item.price - stock_move_needed
            if direction == "CALL":
                target = max(target, option_target)
            else:
                target = min(target, option_target)
        levels.append((label, max(target, 0.01), goal))
    return levels


def format_target_profit_levels(item: Analysis) -> str:
    levels = target_profit_levels(item)
    return " | ".join(f"{label} ${target:.2f} / +{goal}%" for label, target, goal in levels)


def option_spread_pct(option: OptionContract | None) -> float | None:
    mid = option_mid_price(option)
    if option is None or mid is None or mid <= 0 or option.bid is None or option.ask is None:
        return None
    return (option.ask - option.bid) / mid


def option_days_to_expiration(option: OptionContract | None) -> int | None:
    if option is None:
        return None
    return (option.expiration - dt.datetime.now().astimezone().date()).days


def option_trade_plan(item: Analysis, target_pct: float = 0.20, stop_pct: float = 0.25) -> str:
    direction = item.setup_direction or "CALL"
    levels = target_profit_levels(item)
    first_target = levels[0][1] if levels else None
    target_text = f"first trim/exit at +{target_pct:.0%}"
    if first_target:
        target_text += f" near ${first_target:.2f} underlying"
    spread = option_spread_pct(item.option)
    spread_text = ""
    if spread is not None and spread > 0.35:
        spread_text = " Spread is wide, so use a limit order or skip if the fill is poor."
    return (
        f"Long {direction} only. No 0DTE. Plan for a short swing, usually 1-5 trading days: "
        f"{target_text}; cut the contract around -{stop_pct:.0%} to -30% or if the chart trigger fails."
        f"{spread_text}"
    )


def parse_event_timestamp(value: str) -> dt.datetime | None:
    if not value:
        return None
    text = value.strip()
    candidates = [
        text,
        text.replace("Z", "+00:00"),
    ]
    for candidate in candidates:
        try:
            parsed = dt.datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed
        except ValueError:
            continue
    return None


def classify_event_type(title: str) -> str:
    text = title.lower()
    if any(contains_keyword(text, keyword) for keyword in EARNINGS_GUIDANCE_KEYWORDS):
        return "EARNINGS_GUIDANCE"
    if any(contains_keyword(text, keyword) for keyword in DEAL_CONTRACT_KEYWORDS):
        return "CONTRACT_WIN"
    if any(contains_keyword(text, keyword) for keyword in REGULATORY_LEGAL_KEYWORDS):
        return "LEGAL_REGULATORY"
    if any(contains_keyword(text, keyword) for keyword in PRODUCT_TECH_KEYWORDS):
        return "PRODUCT_TECH"
    if any(contains_keyword(text, keyword) for keyword in GEOPOLITICAL_KEYWORDS):
        return "GEOPOLITICAL"
    if any(contains_keyword(text, keyword) for keyword in HYPE_KEYWORDS):
        return "SOCIAL_MOMENTUM"
    if "upgrade" in text or "downgrade" in text or "price target" in text:
        return "ANALYST_ACTION"
    return "MARKET_NEWS"


def classify_event_direction(title: str, setup_direction: str = "") -> str:
    text = title.lower()
    positive = any(contains_keyword(text, keyword) for keyword in POSITIVE_CATALYST_KEYWORDS)
    negative = any(contains_keyword(text, keyword) for keyword in NEGATIVE_CATALYST_KEYWORDS)
    geopolitical = any(contains_keyword(text, keyword) for keyword in GEOPOLITICAL_KEYWORDS)
    if positive and not negative:
        return "BULLISH"
    if negative and not positive:
        return "BEARISH"
    if geopolitical:
        return "VOLATILITY"
    if setup_direction == "CALL":
        return "BULLISH"
    if setup_direction == "PUT":
        return "BEARISH"
    return "UNKNOWN"


def source_credibility_score(source: str) -> float:
    if not source:
        return 45.0
    if any(source.lower() == preferred.lower() for preferred in PREFERRED_NEWS_SOURCES):
        return 82.0
    if any(preferred.lower() in source.lower() for preferred in PREFERRED_NEWS_SOURCES):
        return 78.0
    return 58.0


def event_transmission_path(item: Analysis, event_type: str, direction: str) -> list[str]:
    sector = SYMBOL_SECTORS.get(item.symbol.upper(), "stock")
    if event_type == "GEOPOLITICAL":
        if sector == "energy":
            return ["geopolitical stress", "oil/supply risk", "cash-flow expectations", item.symbol]
        if sector == "semis":
            return ["geopolitical stress", "supply-chain/export-control risk", "multiple pressure", item.symbol]
        return ["geopolitical stress", "risk appetite", "sector rotation", item.symbol]
    if event_type == "EARNINGS_GUIDANCE":
        return ["earnings/guidance update", "forward estimates", "valuation/positioning", item.symbol]
    if event_type == "CONTRACT_WIN":
        return ["deal/contract signal", "future revenue visibility", "demand validation", item.symbol]
    if event_type == "PRODUCT_TECH":
        return ["product/technology news", "growth narrative", "multiple/earnings expectations", item.symbol]
    if event_type == "LEGAL_REGULATORY":
        return ["legal/regulatory event", "risk premium", "earnings uncertainty", item.symbol]
    if event_type == "ANALYST_ACTION":
        return ["analyst action", "estimate/sentiment reset", "near-term positioning", item.symbol]
    if direction == "VOLATILITY":
        return ["market news", "uncertainty", "volatility repricing", item.symbol]
    return ["market news", "expectation change", "price discovery", item.symbol]


def normalize_event(news_item: NewsItem, item: Analysis, index: int = 0) -> NormalizedEvent:
    event_type = classify_event_type(news_item.title)
    direction = classify_event_direction(news_item.title, item.setup_direction)
    credibility = source_credibility_score(news_item.source)
    novelty = 65.0 if index == 0 else max(25.0, 60.0 - index * 5)
    event_time = parse_event_timestamp(news_item.published)
    urgency = 70.0
    if event_time:
        age_hours = max(0.0, (dt.datetime.now(dt.timezone.utc) - event_time.astimezone(dt.timezone.utc)).total_seconds() / 3600)
        urgency = 85.0 if age_hours <= 6 else 70.0 if age_hours <= 24 else 50.0 if age_hours <= 72 else 25.0
    confidence = clamp((credibility * 0.45) + (novelty * 0.25) + (urgency * 0.20) + (10 if direction != "UNKNOWN" else 0))
    event_seed = f"{item.symbol}|{event_type}|{news_item.title}|{news_item.source}|{news_item.published}"
    event_digest = hashlib.sha1(event_seed.encode("utf-8")).hexdigest()[:12]
    event_id = f"{item.symbol}:{event_type}:{event_digest}"
    path = event_transmission_path(item, event_type, direction)
    summary = f"{event_type.replace('_', ' ').title()} event for {item.symbol}: {' -> '.join(path)}."
    return NormalizedEvent(
        event_id=event_id,
        ticker=item.symbol,
        source=news_item.source or "unknown",
        headline=news_item.title,
        event_type=event_type,
        direction=direction,
        confidence=round(confidence, 1),
        novelty_score=round(novelty, 1),
        urgency_score=round(urgency, 1),
        timestamp=news_item.published,
        transmission_path=path,
        summary=summary,
    )


def normalize_events_for_item(item: Analysis, limit: int = 8) -> list[NormalizedEvent]:
    company_news = relevant_company_news(item.news, item)
    if not company_news:
        company_news = item.news[:limit]
    macro_news = relevant_macro_news(item.macro_news or [], item.symbol)
    combined = dedupe_news(company_news + macro_news)
    events = [normalize_event(news_item, item, index) for index, news_item in enumerate(combined[:limit])]
    return sorted(events, key=lambda event: (event.confidence, event.novelty_score, event.urgency_score), reverse=True)


def expected_stock_move_pct(item: Analysis) -> float | None:
    if item.price <= 0:
        return None
    atr = average_true_range(item.chart_highs or [], item.chart_lows or [], item.chart_closes or [])
    if atr:
        base = atr / item.price
    elif item.volatility:
        base = item.volatility / math.sqrt(252)
    else:
        return None
    catalyst_boost = 1.0
    if item.catalyst_score is not None:
        catalyst_boost += max(0.0, item.catalyst_score - 55.0) / 100.0
    return round(max(0.005, base * catalyst_boost), 4)


def current_implied_move_pct(item: Analysis) -> float | None:
    option = item.option
    if option is None:
        return None
    dte = option_days_to_expiration(option)
    if dte is None or dte <= 0:
        return None
    if option.implied_volatility is not None:
        return round(max(0.0, option.implied_volatility * math.sqrt(dte / 365)), 4)
    mid = option_mid_price(option)
    if mid is not None and item.price > 0:
        return round(max(0.0, mid / item.price), 4)
    return None


def social_only_thesis(events: list[NormalizedEvent]) -> bool:
    if not events:
        return False
    return all(event.event_type == "SOCIAL_MOMENTUM" for event in events[:3])


def opportunity_rejection_engine(item: Analysis) -> OpportunityRejection:
    events = item.normalized_events if item.normalized_events is not None else normalize_events_for_item(item)
    expected_move = expected_stock_move_pct(item)
    implied_move = current_implied_move_pct(item)
    edge = None
    if expected_move is not None and implied_move is not None:
        spread_cost = option_spread_pct(item.option) or 0.0
        edge = round(expected_move - implied_move - min(spread_cost, 0.5) * 0.10, 4)
    reasons: list[str] = []
    option_score, option_missing, option_risks = option_chain_quality(item.option, item)
    spread = option_spread_pct(item.option)
    if item.option is None:
        reasons.append("NO_TRADE: live option contract unavailable")
    if item.option and item.option.estimated:
        reasons.append("WATCH: option contract is estimated, not verified live")
    if option_score < 45:
        reasons.append("NO_TRADE: option contract quality is too weak")
    elif option_score < 60:
        reasons.append("WATCH: option contract quality is only average")
    if spread is not None and spread > 0.40:
        reasons.append("NO_TRADE: bid/ask spread likely destroys edge")
    if likely_earnings_window(item) and item.option and item.option.implied_volatility is not None and item.option.implied_volatility >= 0.85:
        reasons.append("WATCH: earnings IV inflation may favor volatility structures over straight directional longs")
    if implied_move is not None and expected_move is not None and implied_move > expected_move * 1.45 and (item.catalyst_score or 50.0) < 82:
        reasons.append("NO_TRADE: options market appears to price more movement than the current edge estimate")
    if item.catalyst_score is not None and item.catalyst_score < 55:
        reasons.append("WATCH: catalyst support is too weak for a forced entry")
    if social_only_thesis(events):
        reasons.append("NO_TRADE: social-only thesis without credible confirmation")
    if events and max(event.confidence for event in events) < 45:
        reasons.append("WATCH: event confidence is low")
    if not events:
        reasons.append("WATCH: no normalized catalyst event available")
    no_trade = any(reason.startswith("NO_TRADE") for reason in reasons)
    if no_trade:
        action = "NO_TRADE"
    elif reasons:
        action = "WATCH"
    else:
        action = "ALERT"
    if not reasons:
        reasons.append("ALERT: practical data does not trigger a rejection rule; entry still requires chart confirmation")
    return OpportunityRejection(
        action=action,
        reasons=list(dict.fromkeys(reasons + option_risks[:3] + option_missing[:2])),
        expected_move_pct=expected_move,
        implied_move_pct=implied_move,
        estimated_edge_pct=edge,
    )


def likely_earnings_window(item: Analysis) -> bool:
    text = " ".join(news_item.title for news_item in item.news[:12]).lower()
    if any(keyword in text for keyword in ("earnings date", "reports earnings", "earnings report", "q1 earnings", "q2 earnings", "q3 earnings", "q4 earnings")):
        return True
    if any(keyword in text for keyword in ("earnings", "guidance", "quarterly results")):
        return True
    return False


def earnings_iv_adjustment(item: Analysis) -> tuple[float, list[str], list[str]]:
    option = item.option
    if option is None:
        return 0.0, ["Earnings date / IV event calendar"], []
    risks: list[str] = []
    missing: list[str] = []
    adjustment = 0.0
    earnings_window = likely_earnings_window(item)
    high_iv = option.implied_volatility is not None and option.implied_volatility >= 0.85
    very_high_iv = option.implied_volatility is not None and option.implied_volatility >= 1.20
    if option.implied_volatility is None:
        missing.append("Live implied volatility for earnings-IV check")
    if not earnings_window:
        missing.append("Confirmed next earnings date")
    if earnings_window and high_iv:
        adjustment -= 12.0 if very_high_iv else 8.0
        risks.append("Earnings/IV inflation detected; this may be a volatility trade, not a clean directional long-option setup")
    elif earnings_window:
        adjustment -= 4.0
        risks.append("Earnings risk is nearby or active; directional entries need extra confirmation")
    elif very_high_iv:
        adjustment -= 6.0
        risks.append("IV is very rich even without a confirmed earnings window")
    return adjustment, missing, risks


def option_chain_quality(option: OptionContract | None, item: Analysis | None = None) -> tuple[float, list[str], list[str]]:
    if option is None:
        return 30.0, ["Live option chain unavailable"], ["No live contract attached"]
    score = 50.0
    risks: list[str] = []
    missing: list[str] = []
    if option.estimated:
        score -= 18
        risks.append("Contract structure is estimated, so live chain verification is required")
    spread = option_spread_pct(option)
    if spread is None:
        missing.append("Bid/ask spread")
        score -= 8
    elif spread <= 0.15:
        score += 18
    elif spread <= 0.25:
        score += 10
    elif spread <= 0.40:
        score -= 8
        risks.append("Bid/ask spread is usable but not clean")
    else:
        score -= 22
        risks.append("Bid/ask spread is wide")
    if option.volume is None:
        missing.append("Contract volume")
    elif option.volume >= 1000:
        score += 12
    elif option.volume >= 100:
        score += 6
    else:
        score -= 8
        risks.append("Contract volume is thin")
    if option.open_interest is None:
        missing.append("Open interest")
    elif option.open_interest >= 1000:
        score += 12
    elif option.open_interest >= 250:
        score += 6
    else:
        score -= 8
        risks.append("Open interest is thin")
    if option.implied_volatility is None:
        missing.append("Implied volatility")
    elif option.implied_volatility > 1.2:
        score -= 16
        risks.append("Implied volatility is very high")
    elif option.implied_volatility > 0.85:
        score -= 8
        risks.append("Implied volatility is elevated")
    elif option.implied_volatility < 0.25:
        score += 5
    dte = option_days_to_expiration(option)
    if dte is None:
        missing.append("Days to expiration")
    elif dte < 7:
        score -= 20
        risks.append("Expiration is too close for the short-swing plan")
    elif dte < 14:
        score -= 8
        risks.append("Expiration is close; theta risk is high")
    elif dte <= 45:
        score += 8
    else:
        score -= 4
        risks.append("Expiration may be too far out for the intended short swing")
    if item is not None and item.price > 0:
        moneyness = abs(option.strike - item.price) / item.price
        if moneyness <= 0.03:
            score += 8
        elif moneyness <= 0.08:
            score += 2
        else:
            score -= 12
            risks.append("Strike is far from spot for a short-term directional trade")
    earnings_adjustment, earnings_missing, earnings_risks = earnings_iv_adjustment(item) if item is not None else (0.0, [], [])
    score += earnings_adjustment
    missing.extend(earnings_missing)
    risks.extend(earnings_risks)
    return clamp(score), missing, risks


def sector_relative_context(item: Analysis) -> tuple[float, list[str], list[str], list[str]]:
    sector = SYMBOL_SECTORS.get(item.symbol.upper(), "")
    benchmark = SECTOR_BENCHMARKS.get(sector)
    if not benchmark:
        return 0.0, [], [], ["Sector benchmark unavailable"]
    try:
        series = fetch_price_series(benchmark, days=80)
    except Exception:
        return 0.0, [], [], [f"Sector benchmark data unavailable for {benchmark}"]
    sector_return = pct_change(series.closes, 20)
    if sector_return is None or item.return_20d is None:
        return 0.0, [], [], [f"Sector-relative 20-day return unavailable for {benchmark}"]
    relative = item.return_20d - sector_return
    direction = item.setup_direction or "CALL"
    bullish: list[str] = []
    bearish: list[str] = []
    risks: list[str] = []
    adjustment = 0.0
    if direction == "CALL":
        if sector_return < -0.03:
            adjustment -= 10.0
            risks.append(f"{benchmark} sector tape is weak, reducing confidence in bullish follow-through")
        if relative > 0.03:
            adjustment += 7.0
            bullish.append(f"Stock is outperforming {benchmark} over 20 days")
        elif relative < -0.03:
            adjustment -= 7.0
            bearish.append(f"Stock is underperforming {benchmark} over 20 days")
    elif direction == "PUT":
        if sector_return > 0.03:
            adjustment -= 8.0
            risks.append(f"{benchmark} sector tape is strong, reducing confidence in bearish follow-through")
        if relative < -0.03:
            adjustment += 7.0
            bearish.append(f"Stock is underperforming {benchmark} over 20 days")
        elif relative > 0.03:
            adjustment -= 7.0
            bullish.append(f"Stock is outperforming {benchmark} over 20 days")
    return adjustment, bullish, bearish, risks


def flow_persistence_context(item: Analysis) -> tuple[float, list[str], list[str], list[str]]:
    option = item.option
    missing = ["Options-flow persistence history"]
    bullish: list[str] = []
    bearish: list[str] = []
    risks: list[str] = []
    adjustment = 0.0
    if option and option.volume is not None and option.open_interest is not None and option.open_interest > 0:
        vol_oi = option.volume / option.open_interest
        if vol_oi >= 1.5:
            risks.append("Single-session option volume is high versus open interest, but persistence is unconfirmed")
            adjustment -= 4.0
        elif vol_oi >= 0.35:
            if option.side == "CALL":
                bullish.append("Contract volume is active versus open interest")
            else:
                bearish.append("Contract volume is active versus open interest")
            adjustment += 2.0
    return adjustment, bullish, bearish, risks + missing


def volatility_quality(item: Analysis) -> tuple[float, list[str], list[str]]:
    missing: list[str] = []
    risks: list[str] = []
    score = 55.0
    if item.volatility is None:
        missing.append("Realized volatility")
    elif item.volatility < 0.18:
        score -= 8
        risks.append("Realized volatility may be too low for a fast option move")
    elif item.volatility <= 0.55:
        score += 14
    else:
        score -= 10
        risks.append("Realized volatility is elevated enough to increase whipsaw risk")
    if item.volume_ratio is None:
        missing.append("Relative volume")
    elif item.volume_ratio >= 1.5:
        score += 14
    elif item.volume_ratio >= 1.1:
        score += 7
    elif item.volume_ratio < 0.8:
        score -= 10
        risks.append("Volume confirmation is light")
    option = item.option
    if option is None or option.implied_volatility is None:
        missing.append("Live implied volatility")
    elif option.implied_volatility > 1.2:
        score -= 12
        risks.append("Option IV is rich, so the contract needs stronger follow-through")
    elif option.implied_volatility < 0.35:
        score += 5
    return clamp(score), missing, risks


def directional_price_action_scores(item: Analysis) -> tuple[float, float, list[str], list[str], list[str]]:
    setup = item.setup_score if item.setup_score is not None else 50.0
    call_score = 50.0
    put_score = 50.0
    bullish: list[str] = []
    bearish: list[str] = []
    risks: list[str] = []
    direction = item.setup_direction or ""
    if direction == "CALL":
        call_score = setup
        put_score = max(20.0, 100.0 - setup * 0.65)
        bullish.extend((item.setup_notes or item.notes)[:3])
    elif direction == "PUT":
        put_score = setup
        call_score = max(20.0, 100.0 - setup * 0.65)
        bearish.extend((item.setup_notes or item.notes)[:3])
    else:
        risks.append("No clean call/put direction from available price action")
    if item.sma_50 and item.sma_200:
        if item.price > item.sma_50 > item.sma_200:
            call_score += 8
            bullish.append("Price is above rising intermediate/long-term moving averages")
        elif item.price < item.sma_50 < item.sma_200:
            put_score += 8
            bearish.append("Price is below falling intermediate/long-term moving averages")
    if item.return_20d is not None:
        if item.return_20d > 0.05:
            call_score += 5
            bullish.append("20-day relative trend is positive")
        elif item.return_20d < -0.05:
            put_score += 5
            bearish.append("20-day relative trend is negative")
    if item.rsi is not None:
        if item.rsi > 74:
            risks.append("RSI is stretched; chasing calls is lower quality")
            call_score -= 6
        elif item.rsi < 26:
            risks.append("RSI is washed out; chasing puts is lower quality")
            put_score -= 6
    return clamp(call_score), clamp(put_score), bullish, bearish, risks


def market_context_directional_scores(item: Analysis) -> tuple[float, float, list[str], list[str], list[str]]:
    catalyst = item.catalyst_score if item.catalyst_score is not None else 50.0
    call_score = catalyst
    put_score = catalyst
    bullish: list[str] = []
    bearish: list[str] = []
    risks: list[str] = []
    direction = item.setup_direction or ""
    if item.catalyst_score is None:
        risks.append("Catalyst score unavailable")
    elif direction == "CALL":
        bullish.append(item.catalyst_label or "Catalyst backdrop supports the call thesis")
        put_score = max(20.0, 100.0 - catalyst * 0.55)
    elif direction == "PUT":
        bearish.append(item.catalyst_label or "Catalyst backdrop supports the put thesis")
        call_score = max(20.0, 100.0 - catalyst * 0.55)
    shock = macro_oil_shock(item.macro_news or [])
    sector = SYMBOL_SECTORS.get(item.symbol.upper(), "")
    if shock.get("active"):
        if sector == "energy":
            call_score += 8
            put_score -= 12
            bullish.append("Active oil/geopolitical shock can support energy calls")
        else:
            call_score -= 14
            put_score += 8
            bearish.append("Active oil/geopolitical shock creates risk-off pressure for non-energy calls")
    return clamp(call_score), clamp(put_score), bullish, bearish, risks


def build_options_opportunity_score(item: Analysis) -> OptionsOpportunityScore:
    price_call, price_put, bullish, bearish, price_risks = directional_price_action_scores(item)
    chain_score, chain_missing, chain_risks = option_chain_quality(item.option, item)
    vol_score, vol_missing, vol_risks = volatility_quality(item)
    context_call, context_put, context_bullish, context_bearish, context_risks = market_context_directional_scores(item)
    sector_adjustment, sector_bullish, sector_bearish, sector_risks = sector_relative_context(item)
    flow_adjustment, flow_bullish, flow_bearish, flow_notes = flow_persistence_context(item)
    rejection = item.opportunity_rejection if item.opportunity_rejection is not None else opportunity_rejection_engine(item)
    bullish.extend(context_bullish)
    bullish.extend(sector_bullish)
    bullish.extend(flow_bullish)
    bearish.extend(context_bearish)
    bearish.extend(sector_bearish)
    bearish.extend(flow_bearish)
    missing = list(dict.fromkeys(chain_missing + vol_missing))
    risks = list(dict.fromkeys(price_risks + chain_risks + vol_risks + context_risks + sector_risks + flow_notes + rejection.reasons))
    institutional_missing = [
        "Options flow: call sweeps, put sweeps, block trades, unusual activity",
        "Dark pool prints",
        "Dealer positioning: GEX, DEX, gamma flip, call wall, put wall, vanna, charm",
        "IV rank / IV percentile",
    ]
    missing.extend(institutional_missing)
    weights = {
        "price": 0.36,
        "chain": 0.29,
        "volatility": 0.21,
        "context": 0.14,
    }
    call_score = (
        price_call * weights["price"]
        + chain_score * weights["chain"]
        + vol_score * weights["volatility"]
        + context_call * weights["context"]
    )
    put_score = (
        price_put * weights["price"]
        + chain_score * weights["chain"]
        + vol_score * weights["volatility"]
        + context_put * weights["context"]
    )
    call_score += sector_adjustment + flow_adjustment
    put_score += sector_adjustment + flow_adjustment
    available_inputs = 4
    if item.option is None or item.option.estimated:
        available_inputs -= 1
    if item.catalyst_score is None:
        available_inputs -= 1
    if item.volatility is None and item.volume_ratio is None:
        available_inputs -= 1
    coverage = max(0.0, available_inputs / 4)
    directional_gap = abs(call_score - put_score)
    confidence = clamp(35 + coverage * 35 + min(20, directional_gap * 0.35) - min(24, len(risks) * 3))
    if rejection.action == "NO_TRADE":
        confidence = min(confidence, 42.0)
    elif rejection.action == "WATCH":
        confidence = min(confidence, 68.0)
    direction = "CALL" if call_score >= put_score else "PUT"
    leading_score = max(call_score, put_score)
    risk_text = " ".join(risks[:2]) if risks else "No major practical-data risk fired, but the trade still requires trigger confirmation."
    summary = (
        f"Practical options score favors {direction} at {leading_score:.0f}/100 using available data only. "
        f"Confidence is {confidence:.0f}/100 because Atlas has price action, chain/volatility proxies, and catalyst context, "
        "but does not have live institutional flow or dealer-positioning feeds."
    )
    if rejection.action != "ALERT":
        summary += f" Rejection engine status: {rejection.action}."
    invalidation: list[str] = []
    if item.trade_brief and item.trade_brief.invalidation is not None:
        invalidation.append(f"Invalid below/above the trade invalidation level near {format_price(item.trade_brief.invalidation)}")
    if item.entry_plan:
        invalidation.append("Invalid if the entry trigger fails or reverses quickly after entry")
    if risk_text:
        invalidation.append(risk_text)
    invalidation.extend(rejection.reasons[:2])
    return OptionsOpportunityScore(
        ticker=item.symbol,
        call_score=round(call_score, 1),
        put_score=round(put_score, 1),
        confidence=round(confidence, 1),
        bullish_factors=list(dict.fromkeys([factor for factor in bullish if factor]))[:6],
        bearish_factors=list(dict.fromkeys([factor for factor in bearish if factor]))[:6],
        missing_data=list(dict.fromkeys(missing)),
        risk_factors=risks[:6],
        invalidation_conditions=invalidation[:5],
        summary=summary,
    )


def trend_label(values: list[float], short_window: int, long_window: int) -> str:
    short = moving_average(values, short_window)
    long = moving_average(values, long_window)
    if short is None or long is None:
        return "unavailable"
    if values[-1] > short > long:
        return "bullish"
    if values[-1] < short < long:
        return "bearish"
    return "mixed"


def recent_structure(highs: list[float], lows: list[float]) -> str:
    if len(highs) < 12 or len(lows) < 12:
        return "structure unavailable"
    prior_high = max(highs[-12:-6])
    recent_high = max(highs[-6:])
    prior_low = min(lows[-12:-6])
    recent_low = min(lows[-6:])
    if recent_high > prior_high and recent_low > prior_low:
        return "higher highs and higher lows"
    if recent_high < prior_high and recent_low < prior_low:
        return "lower highs and lower lows"
    if recent_low < prior_low and highs[-1] >= prior_high * 0.99:
        return "failed breakdown / reclaim attempt"
    if recent_high > prior_high and lows[-1] <= prior_low * 1.01:
        return "failed breakout / rejection attempt"
    return "mixed structure"


def infer_pattern(item: Analysis) -> tuple[str, str, float | None]:
    if item.pattern_detection:
        detection = item.pattern_detection
        return (
            detection.pattern_type,
            "confirmed by pivot trendlines, convergence, and breakout/breakdown candle",
            detection.confidence,
        )
    notes = item.setup_notes or []
    direction = item.setup_direction or "CALL"
    if any("two-line ascending triangle" in note for note in notes):
        return "Two-line ascending triangle", "flat top with rising lower line", 78.0
    if any("two-line descending triangle" in note for note in notes):
        return "Two-line descending triangle", "falling upper line into flat lower support", 78.0
    if any("two-line falling wedge" in note for note in notes):
        return "Two-line falling wedge", "downward converging lines", 76.0
    if any("two-line rising wedge" in note for note in notes):
        return "Two-line rising wedge", "upward converging lines", 76.0
    if any("two-line bullish pennant" in note for note in notes):
        return "Two-line bullish pennant", "converging consolidation after strength", 76.0
    if any("two-line bearish pennant" in note for note in notes):
        return "Two-line bearish pennant", "converging consolidation after weakness", 76.0
    if any("two-line pennant compression" in note for note in notes):
        return "Two-line pennant compression", "converging consolidation", 72.0
    if any("inverse head-and-shoulders" in note for note in notes):
        return "Definitive inverse head-and-shoulders", "right shoulder/base forming near neckline", 88.0
    if any("pennant" in note for note in notes):
        pattern = "Bullish pennant" if direction == "CALL" else "Bearish pennant"
        return f"Definitive {pattern.lower()}", "flagpole plus tight converging consolidation", 86.0
    if any("ascending triangle" in note for note in notes):
        return "Definitive ascending triangle", "flat resistance with clearly rising lows", 84.0
    if any("descending triangle" in note for note in notes):
        return "Definitive descending triangle", "flat support with clearly falling highs", 84.0
    if any("wedge" in note for note in notes):
        pattern = "Falling wedge" if direction == "CALL" else "Rising wedge"
        return f"Definitive {pattern.lower()}", "same-direction converging trendlines", 84.0
    if any("trend pullback" in note or "trend bounce" in note for note in notes):
        return "Trend pullback / continuation", "forming at moving-average area", 70.0
    if any("breakout area" in note for note in notes):
        return "Breakout retest / continuation", "pressing a breakout zone", 72.0
    if any("breakdown area" in note for note in notes):
        return "Breakdown retest / continuation", "pressing a breakdown zone", 72.0
    if any("candle rejection" in note for note in notes):
        pattern = "Hammer/rejection candle" if direction == "CALL" else "Shooting-star/rejection candle"
        return pattern, "early confirmation candle printed", 72.0
    if any("engulfing" in note for note in notes):
        pattern = "Bullish engulfing attempt" if direction == "CALL" else "Bearish engulfing attempt"
        return pattern, "partial confirmation", 70.0
    if any("support" in note for note in notes):
        return "Support reclaim / double-bottom candidate", "forming near support", 64.0
    if any("resistance" in note for note in notes):
        return "Resistance rejection / double-top candidate", "forming near resistance", 64.0
    if item.setup_strategy == "patterns":
        return "Multi-timeframe pattern candidate", "needs intraday confirmation", 58.0
    return "Trend-reversal candidate", "incomplete until entry trigger confirms", 55.0


def support_resistance_text(item: Analysis) -> tuple[str, float | None, float | None]:
    highs = item.chart_highs or []
    lows = item.chart_lows or []
    if len(highs) < 21 or len(lows) < 21:
        return "Not enough history to define reliable levels.", None, None
    support = min(lows[-21:-1])
    resistance = max(highs[-21:-1])
    text = f"Key 20-session support is near ${support:.2f}; key 20-session resistance is near ${resistance:.2f}."
    if len(highs) >= 60 and len(lows) >= 60:
        text += f" Wider 60-session range is ${min(lows[-60:]):.2f} to ${max(highs[-60:]):.2f}."
    return text, support, resistance


def trade_levels(item: Analysis) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    direction = item.setup_direction or "CALL"
    levels = target_profit_levels(item)
    target_1 = levels[0][1] if len(levels) > 0 else None
    target_2 = levels[1][1] if len(levels) > 1 else None
    target_3 = levels[2][1] if len(levels) > 2 else None
    _text, support, resistance = support_resistance_text(item)
    atr = average_true_range(item.chart_highs or [], item.chart_lows or [], item.chart_closes or [])
    buffer = atr * 0.35 if atr else item.price * 0.01
    if direction == "CALL":
        stop = (support - buffer) if support else item.price * 0.975
        invalidation = stop
        reward = (target_1 - item.price) if target_1 else None
        risk = item.price - stop
    else:
        stop = (resistance + buffer) if resistance else item.price * 1.025
        invalidation = stop
        reward = (item.price - target_1) if target_1 else None
        risk = stop - item.price
    risk_reward = (reward / risk) if reward is not None and risk > 0 else None
    return stop, target_1, target_2, target_3, invalidation, risk_reward


def timeframe_alignment(item: Analysis) -> tuple[list[str], list[str], float]:
    direction = item.setup_direction or "CALL"
    supporting: list[str] = []
    opposing: list[str] = []
    checks: list[tuple[str, str]] = [
        ("Monthly", "bullish" if (item.return_3m or 0) > 0 else "bearish" if (item.return_3m or 0) < -0.03 else "mixed"),
        ("Weekly", "bullish" if (item.return_20d or 0) > 0 else "bearish" if (item.return_20d or 0) < 0 else "mixed"),
        ("Daily", trend_label(item.chart_closes or [], 20, 50)),
        ("15m", trend_label(item.intraday_closes or [], 8, 20)),
    ]
    wanted = "bullish" if direction == "CALL" else "bearish"
    for label, state in checks:
        if state == wanted:
            supporting.append(f"{label} {state}")
        elif state in {"bullish", "bearish"}:
            opposing.append(f"{label} {state}")
    available = len(supporting) + len(opposing)
    score = 50.0 if not available else 100.0 * len(supporting) / available
    if supporting and not opposing:
        score = min(100.0, score + 10)
    return supporting, opposing, round(score, 1)


def category_scores(item: Analysis, risk_reward: float | None, market: dict[str, float | bool | str]) -> dict[str, float]:
    notes = item.setup_notes or []
    direction = item.setup_direction or "CALL"
    structure_text = recent_structure(item.chart_highs or [], item.chart_lows or [])
    structure_score = 55.0
    if direction == "CALL" and any(word in structure_text for word in ("higher", "reclaim", "failed breakdown")):
        structure_score = 82.0
    elif direction == "PUT" and any(word in structure_text for word in ("lower", "rejection", "failed breakout")):
        structure_score = 82.0
    elif "mixed" in structure_text:
        structure_score = 58.0
    supporting, opposing, mtf_score = timeframe_alignment(item)
    pattern_score = infer_pattern(item)[2] or 55.0
    volume_score = 50.0
    if item.volume_ratio is not None:
        volume_score = 85.0 if item.volume_ratio >= 1.5 else 72.0 if item.volume_ratio >= 1.1 else 42.0
    relative_score = 62.0
    if direction == "CALL":
        if item.return_20d is not None and item.return_20d > -0.08 and item.price > (item.sma_200 or 0):
            relative_score = 72.0
    else:
        if item.return_20d is not None and item.return_20d > 0.04:
            relative_score = 66.0
    spread = option_spread_pct(item.option)
    options_score = 45.0 if item.option is None or item.option.estimated else 60.0
    if spread is not None:
        options_score = 75.0 if spread <= 0.18 else 62.0 if spread <= 0.35 else 40.0
    catalyst_score = item.catalyst_score if item.catalyst_score is not None else 50.0
    market_score = 58.0
    sector = SYMBOL_SECTORS.get(item.symbol.upper(), "")
    if market.get("oil_shock"):
        if direction == "CALL":
            market_score = 70.0 if sector == "energy" else 28.0
        elif direction == "PUT":
            market_score = 35.0 if sector == "energy" else 70.0
    elif direction == "CALL" and market.get("bullish"):
        market_score = 72.0
    elif direction == "PUT" and market.get("bearish"):
        market_score = 72.0
    elif market.get("available"):
        market_score = 42.0
    rr_score = 40.0
    if risk_reward is not None:
        rr_score = 92.0 if risk_reward >= 3 else 76.0 if risk_reward >= 2 else 45.0
    return {
        "Market Structure": structure_score,
        "Multi-Timeframe Alignment": mtf_score,
        "Pattern Quality": pattern_score,
        "Volume Confirmation": volume_score,
        "Relative Strength": relative_score,
        "Options Flow": options_score,
        "Catalyst Strength": catalyst_score,
        "Market Environment": market_score,
        "Risk/Reward": rr_score,
    }


def weighted_trade_score(scores: dict[str, float]) -> float:
    weights = {
        "Market Structure": 0.20,
        "Multi-Timeframe Alignment": 0.15,
        "Pattern Quality": 0.15,
        "Volume Confirmation": 0.15,
        "Relative Strength": 0.10,
        "Options Flow": 0.10,
        "Catalyst Strength": 0.05,
        "Market Environment": 0.05,
        "Risk/Reward": 0.05,
    }
    return round(sum(scores[key] * weight for key, weight in weights.items()), 1)


def setup_grade_from_confidence(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "Watch"
    return "Wait"


def build_trade_brief(item: Analysis, market: dict[str, float | bool | str] | None = None) -> TradeBrief:
    market = market or {}
    direction = item.setup_direction or "CALL"
    pattern, pattern_status, confirmation = infer_pattern(item)
    stop, target_1, target_2, target_3, invalidation, risk_reward = trade_levels(item)
    scores = category_scores(item, risk_reward, market)
    confidence = weighted_trade_score(scores)
    grade = setup_grade_from_confidence(confidence)
    supporting, opposing, alignment = timeframe_alignment(item)
    sr_text, support, resistance = support_resistance_text(item)
    structure = recent_structure(item.chart_highs or [], item.chart_lows or [])
    notes = "; ".join(item.setup_notes or [])
    take_reasons = [
        f"Pattern/structure: {pattern} with {structure}.",
        f"Chart evidence: {notes or 'setup is mostly technical and still needs confirmation'}.",
        f"Defined first target: ${target_1:.2f} with invalidation near ${invalidation:.2f}." if target_1 and invalidation else "Defined target/invalidation could not be fully calculated.",
    ]
    avoid_reasons: list[str] = []
    if risk_reward is None or risk_reward < 2:
        avoid_reasons.append("Risk/reward is below the required 2:1 threshold.")
    if opposing:
        avoid_reasons.append(f"Opposing timeframes: {', '.join(opposing)}.")
    if item.volume_ratio is not None and item.volume_ratio < 1.0:
        avoid_reasons.append("Volume confirmation is weak.")
    spread = option_spread_pct(item.option)
    if spread is not None and spread > 0.35:
        avoid_reasons.append("Option spread is wide, making fills less favorable.")
    if item.option and item.option.estimated:
        avoid_reasons.append("Live option chain was unavailable; contract is estimated.")
    if item.catalyst_score is not None and item.catalyst_score < 60:
        avoid_reasons.append("Catalyst backdrop is not strongly supportive.")
    event_risk = "Economic calendar feed is not connected; manually check FOMC, CPI, PPI, jobs data, Treasury auctions, and major earnings before entry."
    if risk_reward is not None and risk_reward < 2:
        recommendation = "Wait for a better entry; current risk/reward is not strong enough yet."
    elif grade == "Wait":
        recommendation = "Wait for stronger confirmation before considering this trade."
    elif avoid_reasons:
        recommendation = f"Watch only; take the long {direction} only if the listed trigger confirms and avoid reasons clear."
    else:
        recommendation = f"Actionable watch: long {direction} only on trigger confirmation; first option target is +20%, stop around -25% to -30%."
    setup_family = "trend/pattern" if item.setup_strategy == "patterns" else "trend-reversal" if item.setup_strategy == "reversal" else "breakout/continuation"
    thesis = (
        f"{item.symbol} is a {direction} {setup_family} candidate because price is showing {structure} "
        f"with {pattern.lower()} behavior near a defined level. The setup is valid only if the entry trigger confirms."
    )
    volume_profile = "True volume profile/POC/VAH/VAL feed is not connected; proxy read uses recent support/resistance and volume expansion."
    liquidity = (
        f"Liquidity focus is the ${support:.2f} support and ${resistance:.2f} resistance zone; "
        "a sweep/reclaim around those levels would improve confirmation."
        if support and resistance else "Liquidity levels could not be calculated from available history."
    )
    options_flow = "Live unusual-options-flow, sweeps, gamma walls, and dark-pool data are not connected; report uses live/estimated contract pricing and spread quality only."
    order_flow = "Real tape/order-flow feed is not connected; 15-minute trend reclaim/rejection is used as a proxy confirmation."
    catalyst = expanded_news_summary(item)
    market_env = f"Market regime: {market.get('label', 'unavailable')}. This affects confidence but does not replace the individual chart trigger."
    return TradeBrief(
        thesis=thesis,
        pattern=pattern,
        pattern_status=pattern_status,
        confirmation_level=confirmation,
        measured_move=target_1,
        invalidation=invalidation,
        stop_loss=stop,
        target_1=target_1,
        target_2=target_2,
        target_3=target_3,
        risk_reward=risk_reward,
        market_structure=f"{structure}. {notes}",
        timeframe_supporting=supporting or ["No clear higher/lower timeframe support from available data"],
        timeframe_opposing=opposing,
        alignment_score=alignment,
        indicator_analysis=f"RSI {format_num(item.rsi)}; 50SMA {format_price(item.sma_50)}; 200SMA {format_price(item.sma_200)}; setup grade {score_grade(item.setup_score)}.",
        volume_analysis=f"Relative volume {format_num(item.volume_ratio)}x; volume score {scores['Volume Confirmation']:.0f}/100.",
        relative_strength=f"20-day return {format_pct(item.return_20d)} and 3-month return {format_pct(item.return_3m)} versus market regime context.",
        support_resistance=sr_text,
        volume_profile=volume_profile,
        liquidity_analysis=liquidity,
        options_flow=options_flow,
        order_flow=order_flow,
        catalyst_analysis=catalyst,
        market_environment=market_env,
        event_risk=event_risk,
        bull_case=f"Bull case: price confirms the trigger, holds above invalidation, and reaches Target 1 near {format_price(target_1)} for the +20% option goal.",
        base_case="Base case: price chops near the trigger; wait for confirmation rather than entering early.",
        bear_case=f"Bear case: price fails the trigger or trades through invalidation near {format_price(invalidation)}, which cancels the setup.",
        confidence_score=confidence,
        setup_grade=grade,
        take_reasons=take_reasons,
        avoid_reasons=avoid_reasons or ["No major avoid rule fired, but entry still requires trigger confirmation."],
        final_recommendation=recommendation,
    )


def tradingview_exchange(symbol: str) -> str:
    normalized = symbol.upper()
    nasdaq_symbols = {
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "NFLX", "AVGO",
        "SMCI", "PLTR", "COIN", "MSTR", "ARM", "MU", "INTC", "QCOM", "CRM", "ORCL",
        "ADBE", "NOW", "SHOP", "UBER", "ABNB", "DASH", "SNOW", "CRWD", "PANW", "NET",
        "LLY", "MRNA", "ISRG", "VRTX", "AMGN", "COST", "WMT", "SBUX", "CMG",
    }
    if normalized in nasdaq_symbols:
        return "NASDAQ"
    return "NYSE"


def tradingview_chart_url(symbol: str) -> str:
    normalized = symbol.upper().replace(".", "-")
    exchange = tradingview_exchange(normalized)
    tv_symbol = urllib.parse.quote(f"{exchange}:{normalized}")
    return f"https://www.tradingview.com/chart/?symbol={tv_symbol}"


def rank_score(item: Analysis, mode: str) -> float:
    if mode == "trade":
        if item.final_trade_score is not None:
            return item.final_trade_score
        return item.setup_score if item.setup_score is not None else 0.0
    return item.score


def score_grade(score: float | None) -> str:
    if score is None:
        return "-"
    if score >= 78:
        return "A"
    if score >= 64:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def has_preferred_pattern(item: Analysis) -> bool:
    notes = item.setup_notes or []
    preferred_terms = ("wedge", "pennant", "ascending triangle", "descending triangle", "inverse head-and-shoulders")
    return any(
        "no definitive" not in note
        and "definitive" in note
        and any(term in note for term in preferred_terms)
        for note in notes
    )


def definitive_pattern_notes(notes: list[str] | None) -> list[str]:
    preferred_terms = ("wedge", "pennant", "ascending triangle", "descending triangle", "inverse head-and-shoulders")
    return [
        note
        for note in (notes or [])
        if "no definitive" not in note
        and "definitive" in note
        and any(term in note for term in preferred_terms)
    ]


def market_regime() -> dict[str, float | bool | str]:
    readings: list[dict[str, float | bool | str]] = []
    for symbol in ("SPY", "QQQ"):
        try:
            series = fetch_price_series(symbol, days=260)
        except Exception:
            continue
        sma_50 = moving_average(series.closes, 50)
        return_20d = pct_change(series.closes, 20)
        if sma_50 is None or return_20d is None:
            continue
        readings.append(
            {
                "symbol": symbol,
                "above_50": series.closes[-1] > sma_50,
                "return_20d": return_20d,
            }
        )
    if not readings:
        return {"available": False, "bullish": True, "bearish": False, "label": "market regime unavailable"}
    above_count = sum(1 for item in readings if item["above_50"])
    weak_count = sum(1 for item in readings if float(item["return_20d"]) < -0.03)
    bullish = above_count >= 1 and weak_count == 0
    bearish = above_count == 0 or weak_count >= 2
    label = "bullish/neutral tape" if bullish else "bearish/weak tape" if bearish else "mixed tape"
    return {"available": True, "bullish": bullish, "bearish": bearish, "label": label}


def market_session_state(now: dt.datetime | None = None) -> tuple[bool, str]:
    current = market_now(now)
    if current.weekday() >= 5:
        return False, "Markets are closed"
    open_time = current.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = current.replace(hour=16, minute=0, second=0, microsecond=0)
    if open_time <= current <= close_time:
        return True, "Markets are open"
    return False, "Markets are closed"


def classify_market_trend(spy_closes: list[float], qqq_closes: list[float]) -> tuple[str, str]:
    scores: list[float] = []
    for closes in (spy_closes, qqq_closes):
        clean = [float(value) for value in closes if value is not None and value > 0]
        if len(clean) < 6:
            continue
        latest = clean[-1]
        five_day_return = latest / clean[-6] - 1
        short_average = sum(clean[-5:]) / 5
        slope_score = 1 if latest >= short_average else -1
        scores.append(five_day_return * 100 + slope_score)
    if not scores:
        return "Neutral", "Unknown"
    average_score = sum(scores) / len(scores)
    if average_score >= 2.0:
        return "Bullish", "Strong"
    if average_score >= 0.4:
        return "Bullish", "Moderate"
    if average_score <= -2.0:
        return "Bearish", "Strong"
    if average_score <= -0.4:
        return "Bearish", "Moderate"
    return "Neutral", "Mixed"


def classify_vix(value: float | None) -> str:
    if value is None:
        return "Unknown"
    if value < 14:
        return "Low"
    if value < 22:
        return "Moderate"
    if value < 30:
        return "Elevated"
    return "High"


def fetch_dashboard_closes(symbol: str, days: int = 30, timeout: int = 5) -> list[float]:
    now = int(time.time())
    start = now - days * 24 * 60 * 60
    encoded = urllib.parse.quote(symbol.upper())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={start}&period2={now}&interval=1d&events=history"
    )
    payload = fetch_json(url, timeout=timeout)
    result = payload.get("chart", {}).get("result") or []
    if not result:
        return []
    quote = (result[0].get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    return [float(value) for value in closes if isinstance(value, (int, float)) and value > 0]


def latest_close(symbol: str, days: int = 90) -> float | None:
    try:
        closes = fetch_dashboard_closes(symbol, days=days)
    except Exception:
        return None
    return closes[-1] if closes else None


def dashboard_market_snapshot(use_cache: bool = True, now: dt.datetime | None = None) -> dict[str, Any]:
    current = market_now(now)
    cached_at = float(MARKET_SNAPSHOT_CACHE.get("timestamp") or 0.0)
    cached_value = MARKET_SNAPSHOT_CACHE.get("value")
    if use_cache and cached_value and time.time() - cached_at < 60:
        return dict(cached_value)

    market_open, market_status = market_session_state(current)
    trend = "Neutral"
    strength = "Unknown"
    try:
        spy = fetch_dashboard_closes("SPY", days=30)
        qqq = fetch_dashboard_closes("QQQ", days=30)
        trend, strength = classify_market_trend(spy, qqq)
    except Exception:
        regime = market_regime()
        if regime.get("available"):
            if regime.get("bearish"):
                trend, strength = "Bearish", "Moderate"
            elif regime.get("bullish"):
                trend, strength = "Bullish", "Moderate"

    vix_value = latest_close("^VIX", days=90)
    snapshot: dict[str, Any] = {
        "market_open": market_open,
        "market_status": market_status,
        "trend": trend,
        "strength": strength,
        "volatility": classify_vix(vix_value),
        "vix": round(vix_value, 1) if vix_value is not None else None,
        "updated_at": current.isoformat(),
    }
    MARKET_SNAPSHOT_CACHE["timestamp"] = time.time()
    MARKET_SNAPSHOT_CACHE["value"] = dict(snapshot)
    return snapshot


def setup_has_confirmation(item: Analysis) -> bool:
    notes = set(item.setup_notes or [])
    return bool(
        {
            "green reversal day",
            "3-day stabilization",
            "reversal volume present",
            "bullish candle rejection",
            "bullish engulfing attempt",
            "falling wedge compression",
            "volatility compression near reversal zone",
        }
        & notes
    ) or any("major" in note and "support" in note for note in notes)


def put_has_confirmation(item: Analysis) -> bool:
    notes = set(item.setup_notes or [])
    return bool(
        {
            "red rejection day",
            "3-day rollover",
            "rejection volume present",
            "bearish candle rejection",
            "bearish engulfing attempt",
            "rising wedge compression",
            "volatility compression near reversal zone",
        }
        & notes
    ) or any("major" in note and "resistance" in note for note in notes)


def passes_profit_improvement_filters(item: Analysis, args: argparse.Namespace) -> bool:
    if not getattr(args, "profit_filters", True) or args.mode != "trade" or args.strategy != "reversal":
        return True
    score = item.setup_score or 0
    regime = getattr(args, "market_regime", None) or {}
    if item.setup_direction == "CALL":
        if score < args.min_call_setup_score:
            return False
        if not setup_has_confirmation(item):
            return False
        if regime.get("available") and not regime.get("bullish"):
            return False
        if item.sma_200 and item.price < item.sma_200:
            return False
        return True
    if item.setup_direction == "PUT":
        if score < args.min_put_setup_score:
            return False
        if not put_has_confirmation(item):
            return False
        if regime.get("available") and not regime.get("bearish"):
            return False
        return True
    return False


def passes_post_catalyst_profit_filters(item: Analysis, args: argparse.Namespace) -> bool:
    if not passes_profit_improvement_filters(item, args):
        return False
    if not getattr(args, "profit_filters", True) or args.mode != "trade" or args.strategy != "reversal":
        return True
    if item.setup_direction == "PUT" and getattr(args, "require_put_catalyst", True):
        return (item.catalyst_score or 0) >= args.min_put_catalyst_score
    return True


def apply_intraday_confirmation(item: Analysis) -> None:
    closes = item.intraday_closes or []
    highs = item.intraday_highs or []
    lows = item.intraday_lows or []
    if len(closes) < 24 or len(highs) < 24 or len(lows) < 24:
        return
    direction = item.setup_direction
    sma_8 = moving_average(closes, 8)
    sma_20 = moving_average(closes, 20)
    recent_high = max(highs[-12:-1])
    recent_low = min(lows[-12:-1])
    prior_low = min(lows[-24:-12])
    prior_high = max(highs[-24:-12])
    bonus = 0.0
    notes: list[str] = []
    if direction == "CALL":
        if sma_8 and sma_20 and closes[-1] > sma_8 > sma_20:
            bonus += 4
            notes.append("15m trend reclaim")
        if lows[-1] > prior_low and closes[-1] >= recent_high * 0.995:
            bonus += 4
            notes.append("15m higher-low confirmation")
    elif direction == "PUT":
        if sma_8 and sma_20 and closes[-1] < sma_8 < sma_20:
            bonus += 4
            notes.append("15m trend rejection")
        if highs[-1] < prior_high and closes[-1] <= recent_low * 1.005:
            bonus += 4
            notes.append("15m lower-high confirmation")
    if not bonus:
        return
    item.setup_score = clamp((item.setup_score or 0) + bonus)
    if item.final_trade_score is not None:
        item.final_trade_score = round(clamp(item.final_trade_score + bonus * 0.7), 1)
    setup_notes = list(item.setup_notes or [])
    for note in notes:
        if note not in setup_notes:
            setup_notes.append(note)
    item.setup_notes = setup_notes


def apply_four_hour_pattern_confirmation(item: Analysis) -> bool:
    if item.setup_strategy != "patterns":
        return True
    opens = item.four_hour_opens or []
    highs = item.four_hour_highs or []
    lows = item.four_hour_lows or []
    closes = item.four_hour_closes or []
    volumes = item.four_hour_volumes or []
    if min(len(opens), len(highs), len(lows), len(closes), len(volumes)) < 35:
        return False
    detection = detect_validated_chart_pattern(opens, highs, lows, closes, volumes)
    if detection is None:
        return False

    item.pattern_detection = detection
    item.setup_direction = detection.direction
    item.setup_notes = [detection.pattern_type] + (detection.validation_notes or [])
    display_score = detection.confidence * 100 if detection.confidence <= 1 else detection.confidence
    item.setup_score = clamp(max(item.setup_score or 0, display_score))
    if item.setup_score >= 82:
        item.setup_label = "A validated pattern setup"
    elif item.setup_score >= 68:
        item.setup_label = "B validated pattern setup"
    else:
        item.setup_label = "Watch validated pattern setup"
    item.entry_plan = estimate_entry_plan(
        item.setup_strategy,
        item.setup_direction,
        item.setup_score,
        item.return_1d,
        item.return_5d,
        item.price,
        highs,
        lows,
        closes,
    )
    breakout_index = "pending" if detection.breakout_index is None else str(detection.breakout_index)
    breakout_volume = "-" if detection.breakout_volume_ratio is None else f"{detection.breakout_volume_ratio:.2f}x"
    print(
        f"{item.symbol} validated pattern | Pattern type: {detection.pattern_type} | "
        f"Start/end candle index: {detection.start_index}/{detection.end_index} | "
        f"Trendline slopes: upper {detection.upper_slope:.5f}, lower {detection.lower_slope:.5f} | "
        f"Convergence: {detection.convergence_score:.3f} | "
        f"Breakout candle index: {breakout_index} | "
        f"Breakout volume ratio: {breakout_volume} | "
        f"Confidence score: {detection.confidence:.3f} | "
        f"Pivots: highs {[(index, round(value, 2)) for index, value in (detection.pivot_highs or [])]}, "
        f"lows {[(index, round(value, 2)) for index, value in (detection.pivot_lows or [])]} | "
        f"Validation: {'; '.join(detection.validation_notes or [])}"
    )
    return True


def build_pattern_only_analysis(
    symbol: str,
    name: str,
    labels: list[str],
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[int],
    detection: PatternDetection,
) -> Analysis:
    price = closes[-1]
    display_score = detection.confidence * 100 if detection.confidence <= 1 else detection.confidence
    item = Analysis(
        symbol=symbol,
        name=name or symbol,
        price=price,
        score=display_score,
        rating="Pattern",
        momentum_score=0.0,
        value_score=0.0,
        risk_score=0.0,
        yield_score=0.0,
        return_1y=None,
        return_6m=None,
        return_3m=None,
        volatility=None,
        max_drawdown=None,
        sharpe_like=None,
        rsi=None,
        sma_50=None,
        sma_200=None,
        market_cap=None,
        pe=None,
        dividend_yield=None,
        beta=None,
        notes=detection.validation_notes or [],
        news=[],
        setup_score=clamp(display_score),
        setup_label="Validated forming pattern",
        setup_notes=[detection.pattern_type] + (detection.validation_notes or []),
        setup_direction=detection.direction,
        setup_strategy="patterns",
        chart_dates=labels,
        chart_opens=opens,
        chart_highs=highs,
        chart_lows=lows,
        chart_closes=closes,
        four_hour_dates=labels,
        four_hour_opens=opens,
        four_hour_highs=highs,
        four_hour_lows=lows,
        four_hour_closes=closes,
        four_hour_volumes=volumes,
        pattern_detection=detection,
        final_trade_score=clamp(display_score),
    )
    item.return_1d = pct_change(closes, 1)
    item.return_5d = pct_change(closes, 8)
    item.return_20d = pct_change(closes, 40)
    item.volume_ratio = volumes[-1] / average_volume(volumes, len(volumes) - 1) if average_volume(volumes, len(volumes) - 1) else None
    item.hold_estimate = estimate_hold_window("patterns", item.setup_direction, item.setup_score, item.return_5d, item.return_20d, item.volatility)
    item.entry_plan = estimate_entry_plan(
        "patterns",
        item.setup_direction,
        item.setup_score,
        item.return_1d,
        item.return_5d,
        item.price,
        highs,
        lows,
        closes,
    )
    return item


def pattern_universe(args: argparse.Namespace) -> tuple[list[str], dict[str, str]]:
    symbols = resolve_symbols(args)
    if symbols:
        return symbols, {}
    print("Downloading NASDAQ/NYSE common-stock universe...")
    universe = nyse_nasdaq_universe(fetch_market_universe())
    if args.max_symbols:
        universe = universe[: args.max_symbols]
    names = {item.symbol: item.name for item in universe}
    return [item.symbol for item in universe], names


def run_pattern_scan(args: argparse.Namespace) -> int:
    symbols, universe_names = pattern_universe(args)
    if not symbols:
        print("No NASDAQ/NYSE symbols found.", file=sys.stderr)
        return 2

    allow_visual_fallback = bool(args.symbols or args.watchlist)
    results: list[Analysis] = []
    failed: list[str] = []
    started_at = time.monotonic()
    print(f"Scanning {len(symbols)} NASDAQ/NYSE symbols for forming 4H patterns...")
    for index, symbol in enumerate(symbols, start=1):
        try:
            labels, opens, highs, lows, closes, volumes = fetch_four_hour_ohlcv(symbol)
            detection = detect_validated_chart_pattern(opens, highs, lows, closes, volumes)
            if detection is None and allow_visual_fallback:
                detection = detect_visual_chart_pattern(opens, highs, lows, closes, volumes)
            if detection is None and allow_visual_fallback:
                detection = detect_watchlist_chart_structure(opens, highs, lows, closes, volumes)
            if detection is None:
                maybe_print_progress(index, len(symbols), len(results), started_at, args.progress)
                continue
            if allow_visual_fallback:
                detection = apply_watchlist_pattern_override(symbol, opens, highs, lows, closes, volumes, detection)
            if args.direction == "calls" and detection.direction != "CALL":
                maybe_print_progress(index, len(symbols), len(results), started_at, args.progress)
                continue
            if args.direction == "puts" and detection.direction != "PUT":
                maybe_print_progress(index, len(symbols), len(results), started_at, args.progress)
                continue
            item = build_pattern_only_analysis(symbol, universe_names.get(symbol, symbol), labels, opens, highs, lows, closes, volumes, detection)
            if item.price < args.min_price:
                maybe_print_progress(index, len(symbols), len(results), started_at, args.progress)
                continue
            results.append(item)
            results.sort(key=lambda result: rank_score(result, args.mode), reverse=True)
            if len(results) > args.keep:
                results = results[: args.keep]
            breakout_index = "pending" if detection.breakout_index is None else str(detection.breakout_index)
            breakout_volume = "-" if detection.breakout_volume_ratio is None else f"{detection.breakout_volume_ratio:.2f}x"
            print(
                f"{symbol} forming pattern | Pattern type: {detection.pattern_type} | "
                f"Start/end candle index: {detection.start_index}/{detection.end_index} | "
                f"Trendline slopes: upper {detection.upper_slope:.5f}, lower {detection.lower_slope:.5f} | "
                f"Convergence: {detection.convergence_score:.3f} | "
                f"Breakout candle index: {breakout_index} | "
                f"Breakout volume ratio: {breakout_volume} | "
                f"Confidence score: {detection.confidence:.3f} | "
                f"Pivots: highs {[(pivot_index, round(value, 2)) for pivot_index, value in (detection.pivot_highs or [])]}, "
                f"lows {[(pivot_index, round(value, 2)) for pivot_index, value in (detection.pivot_lows or [])]} | "
                f"Validation: {'; '.join(detection.validation_notes or [])}"
            )
        except Exception as exc:
            failed.append(f"{symbol} ({exc})")
            if args.verbose:
                print(f"Skipped {symbol}: {exc}", file=sys.stderr)
        maybe_print_progress(index, len(symbols), len(results), started_at, args.progress)

    if not results:
        print("No validated forming pattern found", file=sys.stderr)
        output = Path(args.output)
        write_report([], output, args.profile, failed)
        print(f"\nReport written to {output.resolve()}")
        print("Reminder: this is a screening model, not personalized investment advice.")
        return 0

    print(f"Fetching 15-minute confirmation data for {min(len(results), args.keep)} pattern candidates...")
    for item in results[: args.keep]:
        try:
            labels, opens, highs, lows, closes, volumes = fetch_intraday_ohlcv(item.symbol)
            item.intraday_dates = labels
            item.intraday_opens = opens
            item.intraday_highs = highs
            item.intraday_lows = lows
            item.intraday_closes = closes
            item.intraday_volumes = volumes
            apply_intraday_confirmation(item)
        except Exception as exc:
            if args.verbose:
                print(f"15-minute chart unavailable for {item.symbol}: {exc}", file=sys.stderr)

    if args.news or args.catalysts:
        print(f"Fetching recent headlines for {min(len(results), args.limit)} pattern candidates...")
        macro_news = fetch_macro_news() if args.catalysts else []
        deep_research_budget = min(len(results), max(args.limit, 25))
        for research_index, item in enumerate(results[: args.limit]):
            try:
                item.news = fetch_news(item.symbol, limit=40)
                try:
                    if research_index < deep_research_budget:
                        item.news = dedupe_news(fetch_deep_research_news(item.symbol, item.name) + item.news)
                except Exception:
                    pass
            except Exception as exc:
                if args.verbose:
                    print(f"News unavailable for {item.symbol}: {exc}", file=sys.stderr)
                item.news = []
            item.macro_news = macro_news
            item.catalyst_score = None
            item.catalyst_label = "Not screened"
            item.catalyst_notes = ["not used for pattern screening"]

    option_fallbacks: list[str] = []
    if args.options:
        for item in results[: args.limit]:
            try:
                item.option = fetch_option_contract(
                    item.symbol,
                    item.setup_direction or "CALL",
                    item.price,
                    args.min_dte,
                    args.max_dte,
                    args.options_provider,
                )
                if item.option is None:
                    item.option = estimate_option_contract(item.symbol, item.setup_direction or "CALL", item.price, args.min_dte)
                    option_fallbacks.append(f"{item.symbol} (no usable option chain rows)")
                elif item.option.estimated:
                    option_fallbacks.append(f"{item.symbol} (estimated fallback)")
            except Exception as exc:
                item.option = estimate_option_contract(item.symbol, item.setup_direction or "CALL", item.price, args.min_dte)
                option_fallbacks.append(f"{item.symbol} ({exc})")
        if option_fallbacks:
            print("Option fallbacks used: " + "; ".join(option_fallbacks[:10]), file=sys.stderr)

    for item in results[: args.limit]:
        item.trade_brief = build_trade_brief(item, args.market_regime)
        item.normalized_events = normalize_events_for_item(item)
        item.opportunity_rejection = opportunity_rejection_engine(item)
        item.options_opportunity = build_options_opportunity_score(item)
        item.final_trade_score = item.setup_score
    results.sort(key=lambda item: rank_score(item, args.mode), reverse=True)
    print()
    print_table(results, args.limit)
    output = Path(args.output)
    write_report(results[: args.keep], output, args.profile, failed)
    print(f"\nReport written to {output.resolve()}")
    print("Reminder: this is a screening model, not personalized investment advice.")
    return 0


def format_duration(seconds: float | None) -> str:
    if seconds is None or math.isnan(seconds) or math.isinf(seconds):
        return "unknown"
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def print_table(results: list[Analysis], limit: int) -> None:
    headers = ["Rank", "Symbol", "Dir", "Strategy", "Grade", "Chart", "Catalyst", "Setup", "Price", "Strike", "Exp", "Bid/Ask", "Hold Est.", "Entry Plan", "Notes"]
    rows = []
    for rank, item in enumerate(results[:limit], start=1):
        option = item.option
        rows.append(
            [
                str(rank),
                item.symbol,
                item.setup_direction or "-",
                item.setup_strategy or "-",
                score_grade(rank_score(item, "trade")),
                score_grade(item.setup_score if item.setup_score is not None else item.score),
                score_grade(item.catalyst_score),
                item.setup_label or item.rating,
                f"${item.price:.2f}",
                f"{option.strike:.1f}{'e' if option and option.estimated else ''}" if option else "-",
                option.expiration.isoformat() if option else "-",
                format_bid_ask(option),
                item.hold_estimate,
                item.entry_plan,
                "; ".join((item.setup_notes or item.notes)[:2]),
            ]
        )
    widths = [max(len(row[index]) for row in [headers] + rows) for index in range(len(headers))]
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))


def write_report(results: list[Analysis], output: Path, profile: str, failed: list[str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    generated = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    blocks = "\n".join(report_block(rank, item) for rank, item in enumerate(results, start=1))
    if not blocks:
        blocks = """<section class="empty-state">
      <div class="empty-kicker">No Entry-Quality Setups</div>
      <h2>No clean trades passed the final screen.</h2>
      <p>Atlas found market candidates, then rejected them after catalyst, option quality, risk/reward, and execution checks. That is intentional: when the backdrop is messy, the report should stay quiet instead of dressing up weak trades.</p>
    </section>"""
    failed_html = ""
    if failed:
        failed_html = f"<p class=\"warning\">Failed symbols: {html.escape(', '.join(failed))}</p>"
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Current Watchlist</title>
  <style>
    :root {{ color-scheme: dark; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }}
    body {{ margin: 0; background: #020307; color: #eeeeee; }}
    body::before {{ content: ""; position: fixed; inset: 0; pointer-events: none; background: radial-gradient(circle at 50% 18%, rgba(255, 255, 255, .035), transparent 34%); }}
    main {{ position: relative; max-width: none; margin: 0; padding: 0 0 100px; }}
    h1 {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }}
    p {{ margin: 0 0 16px; color: #9b9b9b; }}
    a {{ color: #d6d6d6; }}
    a:visited {{ color: #a8a8a8; }}
    table {{ width: 100%; border-collapse: collapse; background: #111111; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #2a2a2a; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: #1a1a1a; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #b8b8b8; }}
    tr:nth-child(even) td {{ background: #151515; }}
    .score {{ font-weight: 700; }}
    .warning {{ margin-top: 16px; color: #fdba74; }}
    .small {{ font-size: 12px; color: #9b9b9b; max-width: 900px; margin-top: 16px; }}
    .toolbar {{ display: none; }}
    .toolbar button {{ min-height: 38px; border: 1px solid #3a3a3a; border-radius: 4px; background: #050505; color: #eeeeee; font: inherit; font-size: 11px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; padding: 0 14px; cursor: pointer; }}
    .toolbar button:hover {{ border-color: #777777; background: #0d0d0d; }}
    .setups {{ display: grid; gap: 0; margin-top: 0; }}
    .empty-state {{ border: 1px solid #242424; border-radius: 10px; background: #050505; padding: 34px; text-align: center; box-shadow: 0 22px 70px rgba(0, 0, 0, .42); }}
    .empty-kicker {{ color: #8f8f8f; font-size: 11px; font-weight: 900; letter-spacing: .18em; text-transform: uppercase; }}
    .empty-state h2 {{ margin: 10px 0 10px; color: #f2f2f2; font-size: clamp(24px, 4vw, 40px); line-height: 1.05; }}
    .empty-state p {{ max-width: 700px; margin: 0 auto; color: #a8a8a8; line-height: 1.6; }}
    .setup-card {{ background: transparent; border: 0; border-radius: 0; overflow: hidden; box-shadow: none; border-bottom: 1px solid rgba(114, 116, 126, .13); }}
    .setup-card.is-hidden {{ display: none; }}
    .setup-card .setup-body {{ display: grid; grid-template-rows: 1fr; opacity: 1; transition: grid-template-rows .34s cubic-bezier(.2, .8, .2, 1), opacity .24s ease; }}
    .setup-card.is-collapsed .setup-body {{ grid-template-rows: 0fr; opacity: 0; }}
    .setup-body-inner {{ min-height: 0; overflow: hidden; }}
    .setup-summary {{ display: grid; grid-template-columns: minmax(135px, 1fr) minmax(190px, 240px) 142px 28px; align-items: center; min-height: 124px; gap: 32px; padding: 0; background: transparent; border-bottom: 0; }}
    .setup-summary-main {{ display: flex; align-items: center; min-width: 0; }}
    .setup-summary-actions {{ align-self: stretch; display: grid; place-items: center; width: 28px; background: transparent; border-left: 0; }}
    .summary-title-row {{ display: flex; align-items: center; gap: 0; min-width: 0; }}
    .setup-summary .direction {{ display: none; }}
    .summary-symbol {{ font-size: 28px; line-height: 1; font-weight: 400; letter-spacing: -.015em; }}
    .summary-company {{ margin-top: 18px; color: rgba(222, 223, 230, .58); font-size: 21px; line-height: 1.15; font-weight: 400; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 178px; }}
    .sparkline {{ width: 224px; height: 64px; display: block; opacity: .95; }}
    .sparkline-baseline {{ stroke: rgba(214, 218, 226, .36); stroke-width: 1; stroke-dasharray: 2 6; }}
    .sparkline-line {{ fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }}
    .sparkline.positive .sparkline-line {{ stroke: #0caf45; }}
    .sparkline.negative .sparkline-line {{ stroke: #cf5337; }}
    .sparkline.neutral .sparkline-line {{ stroke: rgba(222, 223, 230, .55); }}
    .quote-block {{ min-width: 142px; text-align: center; padding-right: 0; justify-self: end; border: 1.6px solid rgba(226, 226, 232, .34); border-radius: 8px; min-height: 58px; display: grid; place-items: center; padding: 0 16px; background: rgba(2, 3, 7, .94); position: relative; z-index: 1; }}
    .quote-price {{ color: #f4f4f6; font-size: 26px; line-height: 1; font-weight: 400; letter-spacing: .005em; }}
    .quote-change {{ display: none; }}
    .quote-block.positive {{ border-color: rgba(12, 175, 69, .88); }}
    .quote-block.negative {{ border-color: rgba(207, 83, 55, .9); }}
    .quote-block.positive .quote-change {{ color: #72bd70; }}
    .quote-block.negative .quote-change {{ color: #d66d72; }}
    .quote-block.neutral .quote-change {{ color: rgba(226, 226, 232, .55); }}
    .setup-body {{ border-top: 0; }}
    .setup-top {{ display: grid; grid-template-columns: 1fr; gap: 28px; padding: 26px 22px 30px; align-items: start; }}
    .setup-details {{ display: grid; grid-template-columns: minmax(260px, 330px) minmax(0, 1fr); gap: 18px; align-content: start; }}
    .watchlist-preview {{ display: grid; grid-template-columns: 1fr; gap: 12px; }}
    .setup-heading, .setup-actions {{ display: none; }}
    .toggle-card {{ position: relative; width: 100%; height: 100%; border: 0; border-radius: 0; padding: 0; background: transparent; color: rgba(241, 241, 245, .9); cursor: pointer; font-size: 0; }}
    .toggle-card::before {{ content: ""; display: block; width: 9px; height: 9px; margin: 0 auto; border-right: 1.7px solid currentColor; border-bottom: 1.7px solid currentColor; transform: rotate(45deg); transition: transform .22s cubic-bezier(.2, .8, .2, 1); }}
    .setup-card:not(.is-collapsed) .toggle-card::before {{ transform: rotate(225deg); }}
    .toggle-card:hover {{ background: rgba(255, 255, 255, .035); }}
    .setup-rank {{ font-size: 13px; color: #9b9b9b; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }}
    .setup-symbol {{ font-size: 28px; font-weight: 800; line-height: 1; }}
    .setup-name {{ margin-top: 4px; color: #9b9b9b; font-size: 13px; }}
    .direction {{ border-radius: 4px; padding: 3px 8px 2px; font-weight: 600; font-size: 9px; letter-spacing: .04em; }}
    .direction.call {{ background: rgba(20, 39, 23, .56); color: #86d47f; border: 1px solid rgba(112, 197, 105, .52); }}
    .direction.put {{ background: rgba(48, 22, 26, .58); color: #d77078; border: 1px solid rgba(215, 94, 105, .52); }}
    .vital-grid {{ display: grid; grid-template-columns: 1fr; gap: 10px; }}
    .decision-section {{ border: 1px solid #242424; border-radius: 8px; padding: 13px; background: #030303; }}
    .decision-section.recommendation {{ font-size: 13px; line-height: 1.4; }}
    .decision-section.recommendation.reject {{ border-color: #7f1d1d; color: #fecaca; }}
    .decision-section.recommendation.watch {{ border-color: #854d0e; color: #fde68a; }}
    .decision-section.recommendation.action {{ border-color: #14532d; color: #bbf7d0; }}
    .decision-label {{ color: #9b9b9b; font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 5px; }}
    .entry-text {{ color: #eeeeee; line-height: 1.5; font-weight: 650; }}
    .theme-stack {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; align-content: start; }}
    .theme-panel {{ border: 1px solid #242424; border-radius: 8px; background: #030303; overflow: hidden; }}
    .theme-panel summary {{ cursor: pointer; display: flex; justify-content: space-between; gap: 10px; padding: 14px 15px; color: #eeeeee; font-size: 11px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; list-style: none; }}
    .theme-panel summary::-webkit-details-marker {{ display: none; }}
    .theme-panel summary::after {{ content: "Expand"; color: #8f8f8f; font-size: 9px; letter-spacing: .08em; }}
    .theme-panel[open] summary::after {{ content: "Collapse"; }}
    .theme-body {{ border-top: 1px solid #202020; padding: 15px; color: #d6d6d6; font-size: 13px; line-height: 1.55; }}
    .theme-body p {{ margin: 0 0 10px; color: #d6d6d6; }}
    .theme-body p:last-child {{ margin-bottom: 0; }}
    .theme-body ul {{ margin: 0; padding-left: 17px; }}
    .theme-body li + li {{ margin-top: 5px; }}
    .read-more-link {{ display: inline-flex; min-height: 42px; align-items: center; justify-content: center; border: 1px solid #3a3a3a; border-radius: 4px; background: #050505; color: #eeeeee; font-size: 11px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; padding: 0 16px; text-decoration: none; justify-self: start; }}
    .read-more-link:hover {{ border-color: #777777; background: #101010; }}
    button.read-more-link {{ cursor: pointer; font-family: inherit; }}
    body.show-detail .toolbar,
    body.show-detail .setups,
    body.show-detail .small,
    body.show-detail .warning {{ display: none; }}
    .detail-view {{ display: none; }}
    body.show-detail .detail-view {{ display: block; }}
    .detail-page {{ display: none; }}
    .detail-page.is-active {{ display: block; }}
    .back-link {{ display: inline-flex; min-height: 38px; align-items: center; border: 1px solid #333333; border-radius: 999px; padding: 0 14px; color: #d0d0d0; background: #050505; text-decoration: none; font-size: 11px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; cursor: pointer; font-family: inherit; }}
    .hero {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin: 26px 0 22px; }}
    .symbol {{ font-size: clamp(42px, 10vw, 76px); line-height: .9; font-weight: 950; letter-spacing: .01em; }}
    .company {{ margin-top: 10px; color: #9b9b9b; font-size: 15px; font-weight: 700; }}
    .status-card {{ border: 1px solid #262626; border-radius: 10px; background: #050505; padding: 16px; margin-bottom: 18px; }}
    .status-label {{ color: #888888; font-size: 10px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; }}
    .status-value {{ margin-top: 8px; font-size: 22px; font-weight: 900; }}
    .section-grid {{ display: grid; gap: 14px; }}
    .option-plan {{ color: #d0d0d0; line-height: 1.4; }}
    .detail-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .detail {{ border: 1px solid #242424; border-radius: 8px; padding: 13px; background: #030303; }}
    .detail-label {{ color: #868686; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: .12em; }}
    .detail-value {{ margin-top: 6px; font-size: 18px; font-weight: 800; overflow-wrap: anywhere; }}
    .signals {{ border-top: 1px solid #2a2a2a; padding-top: 10px; color: #d0d0d0; font-size: 14px; }}
    .secondary-analysis {{ margin: 0 16px 16px; border: 1px solid #2a2a2a; border-radius: 8px; background: #0b0b0b; overflow: hidden; }}
    .secondary-analysis summary {{ cursor: pointer; padding: 12px 14px; color: #eeeeee; font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: .05em; list-style: none; }}
    .secondary-analysis summary::-webkit-details-marker {{ display: none; }}
    .secondary-analysis summary::after {{ content: "Expand"; float: right; color: #9b9b9b; font-size: 11px; }}
    .secondary-analysis[open] summary::after {{ content: "Collapse"; }}
    .secondary-body {{ border-top: 1px solid #2a2a2a; padding: 14px; display: grid; gap: 12px; }}
    .rationale {{ border: 1px solid #262626; border-radius: 8px; padding: 12px; background: #101010; color: #d6d6d6; line-height: 1.5; }}
    .rationale strong {{ display: block; color: #eeeeee; margin-bottom: 5px; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .rationale p {{ margin: 0 0 10px; color: #d6d6d6; }}
    .rationale p:last-child {{ margin-bottom: 0; }}
    .trade-brief {{ display: grid; gap: 10px; }}
    .brief-title {{ color: #eeeeee; font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: .05em; }}
    .brief-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .brief-section {{ border: 1px solid #262626; border-radius: 8px; padding: 9px; background: #0d0d0d; color: #d0d0d0; font-size: 12px; line-height: 1.4; }}
    .brief-section.full {{ grid-column: 1 / -1; }}
    .brief-section strong {{ color: #eeeeee; display: block; margin-bottom: 4px; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
    .brief-section ul {{ margin: 0; padding-left: 16px; }}
    .brief-section.recommendation {{ border-color: #3f3f46; background: #111111; font-weight: 700; }}
    .brief-section.recommendation.reject {{ border-color: #7f1d1d; color: #fecaca; }}
    .brief-section.recommendation.watch {{ border-color: #854d0e; color: #fde68a; }}
    .brief-section.recommendation.action {{ border-color: #14532d; color: #bbf7d0; }}
    .headline-list {{ display: grid; gap: 9px; margin-top: 6px; }}
    .headline-item {{ color: #d0d0d0; line-height: 1.35; }}
    .headline-source {{ color: #9b9b9b; font-size: 11px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }}
    .headline-title {{ margin-top: 2px; font-weight: 700; }}
    .headline-title a {{ color: #eeeeee; text-decoration: none; }}
    .headline-title a:hover {{ text-decoration: underline; }}
    .headline-impact {{ margin-top: 2px; color: #b8b8b8; }}
    .news-summary {{ color: #d0d0d0; line-height: 1.45; }}
    @media (max-width: 1040px) {{ .setup-details {{ grid-template-columns: 1fr; }} .theme-stack {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 860px) {{ main {{ padding: 0 0 100px; }} .setup-top {{ padding: 18px 14px 22px; }} .vital-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} .detail-value {{ font-size: 15px; }} }}
    @media (max-width: 620px) {{ .setup-summary {{ min-height: 104px; grid-template-columns: 150px 120px 116px 22px; gap: 38px; }} .setup-summary-actions {{ width: 22px; }} .summary-symbol {{ font-size: 22px; }} .summary-company {{ margin-top: 10px; font-size: 15px; max-width: 142px; }} .sparkline {{ width: 120px; height: 45px; }} .quote-block {{ min-width: 116px; min-height: 48px; padding: 0 10px; }} .quote-price {{ font-size: 20px; }} }}
    @media (max-width: 520px) {{ main {{ padding: 0 0 100px; }} .setup-summary {{ width: 100%; min-height: 94px; grid-template-columns: 100px 92px minmax(10px, 1fr) 78px 8px 16px; gap: 0; }} .setup-summary-main {{ grid-column: 1; }} .sparkline {{ grid-column: 2; width: 92px; height: 36px; }} .quote-block {{ grid-column: 4; min-width: 78px; min-height: 36px; padding: 0 7px; }} .setup-summary-actions {{ grid-column: 6; width: 16px; justify-self: end; }} .summary-symbol {{ font-size: 18px; font-weight: 400; }} .summary-company {{ margin-top: 8px; font-size: 12px; max-width: 94px; }} .quote-price {{ font-size: 15px; font-weight: 400; }} .vital-grid {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 390px) {{ .setup-summary {{ width: 100%; grid-template-columns: 96px 90px minmax(0, 1fr) 76px 8px 18px; min-height: 84px; gap: 0; }} .setup-summary-main {{ grid-column: 1; }} .sparkline {{ grid-column: 2; width: 90px; height: 32px; }} .quote-block {{ grid-column: 4; min-width: 76px; min-height: 34px; }} .setup-summary-actions {{ grid-column: 6; width: 18px; justify-self: end; }} .summary-symbol {{ font-size: 17px; }} .summary-company {{ font-size: 11px; max-width: 92px; }} .quote-price {{ font-size: 14px; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Current Watchlist</h1>
    <section class="toolbar" aria-label="Watchlist controls">
      <button type="button" id="collapseAll">Collapse all</button>
      <button type="button" id="expandAll">Expand all</button>
    </section>
    <section class="setups">
      {blocks}
    </section>
    <section class="detail-view" id="detailView" aria-label="Ticker details">
      <button type="button" class="back-link" id="backToWatchlist">Back to Watchlist</button>
      {"".join(detail_article(rank, item) for rank, item in enumerate(results, start=1))}
    </section>
    {failed_html}
  </main>
  <script>
    const cards = Array.from(document.querySelectorAll('.setup-card'));

    function setCollapsed(card, collapsed) {{
      card.classList.toggle('is-collapsed', collapsed);
      const button = card.querySelector('.toggle-card');
      if (button) button.setAttribute('aria-label', (collapsed ? 'Expand ' : 'Collapse ') + card.dataset.symbol);
    }}

    document.getElementById('collapseAll').addEventListener('click', () => {{
      for (const card of cards) setCollapsed(card, true);
    }});
    document.getElementById('expandAll').addEventListener('click', () => {{
      for (const card of cards) setCollapsed(card, false);
    }});

    document.addEventListener('click', (event) => {{
      const readMore = event.target.closest('.read-more-link[data-detail-target]');
      if (readMore) {{
        const target = readMore.dataset.detailTarget;
        openDetail(target);
        return;
      }}
      const toggle = event.target.closest('.toggle-card');
      if (toggle) {{
        const card = toggle.closest('.setup-card');
        const shouldCollapse = !card.classList.contains('is-collapsed');
        setCollapsed(card, shouldCollapse);
        if (!shouldCollapse) {{
          window.setTimeout(() => card.scrollIntoView({{ block: 'center', behavior: 'smooth' }}), 120);
        }}
        return;
      }}
    }});
    function openDetail(symbol) {{
      const pages = Array.from(document.querySelectorAll('.detail-page'));
      let matched = false;
      for (const page of pages) {{
        const active = page.dataset.symbol === symbol;
        page.classList.toggle('is-active', active);
        matched = matched || active;
      }}
      if (!matched && pages[0]) pages[0].classList.add('is-active');
      document.body.classList.add('show-detail');
      document.getElementById('detailView').scrollIntoView({{ block: 'start' }});
    }}
    document.getElementById('backToWatchlist')?.addEventListener('click', () => {{
      const params = new URLSearchParams(window.location.search);
      if (params.get('return') === 'app') {{
        window.location.href = '/app';
        return;
      }}
      document.body.classList.remove('show-detail');
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }});
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Escape') {{
        document.body.classList.remove('show-detail');
        for (const card of cards) setCollapsed(card, true);
      }}
    }});
    const initialParams = new URLSearchParams(window.location.search);
    const initialDetail = initialParams.get('detail') || initialParams.get('symbol') || window.location.hash.replace('#', '');
    if (initialDetail) {{
      window.requestAnimationFrame(() => openDetail(initialDetail.toUpperCase()));
    }}

    function reportScrollProgress() {{
      const progress = Math.max(0, Math.min(1, window.scrollY / 140));
      window.parent?.postMessage({{ type: 'atlas-report-scroll', progress }}, '*');
    }}
    let reportSwipeStartX = 0;
    let reportSwipeStartY = 0;
    document.addEventListener('touchstart', (event) => {{
      const point = event.touches[0];
      reportSwipeStartX = point.clientX;
      reportSwipeStartY = point.clientY;
    }}, {{ passive: true }});
    document.addEventListener('touchend', (event) => {{
      const point = event.changedTouches[0];
      const deltaX = point.clientX - reportSwipeStartX;
      const deltaY = point.clientY - reportSwipeStartY;
      if (Math.abs(deltaX) > 54 && Math.abs(deltaX) > Math.abs(deltaY) * 1.35) {{
        window.parent?.postMessage({{ type: 'atlas-subpanel-swipe', direction: deltaX < 0 ? 'left' : 'right' }}, '*');
      }}
    }}, {{ passive: true }});
    window.addEventListener('scroll', reportScrollProgress, {{ passive: true }});
    reportScrollProgress();
  </script>
</body>
</html>
"""
    output.write_text(document, encoding="utf-8")


def report_block(rank: int, item: Analysis) -> str:
    grade = score_grade(rank_score(item, "trade"))
    direction = item.setup_direction or "-"
    direction_class = direction.lower()
    company_name = display_company_name(item.symbol, item.name)
    search_text = " ".join(
        [
            item.symbol,
            company_name,
            direction,
            grade,
            item.setup_label or item.rating,
            " ".join(item.setup_notes or item.notes),
            " ".join(news_item.title for news_item in item.news[:5]),
            expanded_news_summary(item),
        ]
    )
    change_html = price_change_html(item)
    sparkline_html = watchlist_sparkline_html(item)
    return f"""<article class="setup-card is-collapsed" data-symbol="{html.escape(item.symbol)}" data-grade="{html.escape(grade)}" data-direction="{html.escape(direction)}" data-search="{html.escape(search_text.lower())}">
  <div class="setup-summary">
    <div class="setup-summary-main">
      <div>
        <div class="summary-title-row">
          <div class="summary-symbol">{html.escape(item.symbol)}</div>
          <div class="direction {html.escape(direction_class)}">{html.escape(direction)}</div>
        </div>
        <div class="summary-company">{html.escape(company_name)}</div>
      </div>
    </div>
    {sparkline_html}
    {change_html}
    <div class="setup-summary-actions">
      <button type="button" class="toggle-card" aria-label="Expand {html.escape(item.symbol)}"></button>
    </div>
  </div>
  <div class="setup-body">
    <div class="setup-body-inner">
      <div class="setup-top">
        {watchlist_preview_panel(rank, item)}
      </div>
    </div>
  </div>
</article>"""


def watchlist_sparkline_html(item: Analysis) -> str:
    closes = [value for value in (item.chart_closes or [])[-36:] if value is not None]
    if len(closes) < 2:
        return '<svg class="sparkline neutral" viewBox="0 0 142 42" aria-hidden="true"><line class="sparkline-baseline" x1="2" y1="21" x2="140" y2="21"></line></svg>'
    min_close = min(closes)
    max_close = max(closes)
    price_range = max_close - min_close
    if price_range <= 0:
        price_range = max(abs(max_close) * 0.01, 1.0)
        min_close -= price_range / 2
    width = 142
    height = 42
    pad_x = 3
    pad_y = 5
    usable_w = width - pad_x * 2
    usable_h = height - pad_y * 2
    points = []
    for index, close in enumerate(closes):
        x = pad_x + (index / (len(closes) - 1)) * usable_w
        y = pad_y + (1 - ((close - min_close) / price_range)) * usable_h
        points.append(f"{x:.1f},{y:.1f}")
    trend_class = "positive" if closes[-1] >= closes[0] else "negative"
    return (
        f'<svg class="sparkline {trend_class}" viewBox="0 0 {width} {height}" aria-hidden="true">'
        f'<line class="sparkline-baseline" x1="2" y1="{height / 2:.1f}" x2="{width - 2}" y2="{height / 2:.1f}"></line>'
        f'<polyline class="sparkline-line" points="{html.escape(" ".join(points))}"></polyline>'
        "</svg>"
    )


def price_change_html(item: Analysis) -> str:
    change = item.return_1d
    if change is None:
        return f"""<div class="quote-block neutral">
      <div class="quote-price">${item.price:.2f}</div>
      <div class="quote-change">--</div>
    </div>"""
    previous = item.price / (1 + change) if change > -0.999 else item.price
    dollar_change = item.price - previous
    sign = "+" if dollar_change >= 0 else ""
    change_class = "positive" if dollar_change >= 0 else "negative"
    return f"""<div class="quote-block {change_class}">
      <div class="quote-price">${item.price:.2f}</div>
      <div class="quote-change">{sign}{dollar_change:.2f} ({sign}{change * 100:.2f}%)</div>
    </div>"""


def detail_symbol_id(item: Analysis) -> str:
    safe_symbol = re.sub(r"[^A-Za-z0-9_-]+", "_", item.symbol.upper()).strip("_")
    return safe_symbol or "ticker"


def watchlist_preview_panel(rank: int, item: Analysis) -> str:
    symbol_id = detail_symbol_id(item)
    return f"""<section class="watchlist-preview">
  {theme_panel("Why is it on the list?", why_on_watchlist_text(item), open_panel=True)}
  <button type="button" class="read-more-link" data-detail-target="{html.escape(symbol_id)}">Read More</button>
</section>"""


def why_on_watchlist_text(item: Analysis) -> str:
    brief = item.trade_brief
    direction = item.setup_direction or "-"
    stance = analyst_stance(item, brief)
    evidence = plain_setup_read(item)
    company_name = display_company_name(item.symbol, item.name)
    catalyst_read = plain_catalyst_preview(
        item,
        dedupe_news((relevant_company_news(item.news, item) or item.news) + relevant_macro_news(item.macro_news or [], item.symbol)),
        relevant_macro_news(item.macro_news or [], item.symbol),
    )
    opportunity = item.options_opportunity or build_options_opportunity_score(item)
    rejection = item.opportunity_rejection if item.opportunity_rejection is not None else opportunity_rejection_engine(item)
    primary_risk = (rejection.reasons or opportunity.risk_factors or ["confirmation is still required"])[0]
    contract_read = "The contract side is still estimated or incomplete, so I would verify the chain before treating the setup as actionable."
    if item.option and not item.option.estimated:
        spread = option_spread_pct(item.option)
        if spread is not None and spread <= 0.18:
            contract_read = "The option structure is usable enough to monitor because the spread is not the main problem; the entry trigger is."
        elif spread is not None:
            contract_read = "The stock may be interesting, but the option spread needs discipline because a sloppy fill can erase the edge quickly."
        else:
            contract_read = "The contract has live data, but I would still judge it by fill quality and whether price confirms the trigger."
    if brief:
        status, status_detail = entry_status(item, brief)
        status_note = status_detail.split(".")[0].strip()
        trigger = preview_level_text(item, brief.confirmation_level, "the listed entry trigger")
        invalidation = format_price(brief.invalidation)
        setup_clause = evidence.strip()
        catalyst_clause = clean_preview_catalyst_read(catalyst_read, item.symbol).strip()
        return (
            f"{company_name} is on the live list because the current {direction} idea has a specific place to be right or wrong, not because it is an automatic entry. "
            f"The setup read is: {setup_clause} The outside context is: {catalyst_clause} "
            f"My current stance is {stance}. {status_note}. The level that matters most is {trigger}; if price cannot confirm around that area, I would rather let it go than force the trade. "
            f"The main reason to be careful is this: {primary_risk}. {contract_read} "
            f"I would stop trusting the idea if price breaks the invalidation area near {invalidation}, because at that point the thesis is no longer behaving the way it needs to."
        )
    return (
        f"{company_name} is here as a possible {direction} idea because the scan found enough movement and context to keep it on watch. "
        f"The setup read is: {evidence} The current outside read is: {clean_preview_catalyst_read(catalyst_read, item.symbol)} "
        f"The main caution is {primary_risk}. I would keep this watch-only until the fuller trade details and contract quality are available."
    )


def article_phrase(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "a setup"
    first_word = cleaned.split()[0].lower()
    if first_word in {"a", "an", "the"}:
        return cleaned
    article = "an" if cleaned[0].lower() in {"a", "e", "i", "o", "u"} else "a"
    return f"{article} {cleaned}"


def normalized_setup_phrase(setup: str) -> str:
    phrase = setup.strip().lower()
    grade_match = re.fullmatch(r"([a-d])\s+(.+)", phrase)
    if grade_match:
        return f"grade {grade_match.group(1).upper()} {grade_match.group(2)}"
    return phrase


def clean_preview_catalyst_read(text: str, symbol: str) -> str:
    cleaned = re.sub(
        rf"After reviewing [^.]+?, the story around {re.escape(symbol)} is mainly about ",
        f"The current news flow around {symbol} is mainly about ",
        text,
    )
    cleaned = re.sub(r"\s*Most relevant current item: .*?(?=\s+Macro override:|\s+Trade read:|\s+PUT confirmation:|\s+CALL confirmation:|\s+What would weaken|$)", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def supporting_sources_text(item: Analysis) -> str:
    company_news = relevant_company_news(item.news, item) or item.news
    macro_news = relevant_macro_news(item.macro_news or [], item.symbol)
    research_news = select_research_news(item, company_news, macro_news, limit=8)
    combined = dedupe_news(research_news + company_news + macro_news)
    brief = item.trade_brief
    opportunity = item.options_opportunity or build_options_opportunity_score(item)
    rejection = item.opportunity_rejection if item.opportunity_rejection is not None else opportunity_rejection_engine(item)
    catalyst_read = plain_catalyst_preview(item, combined, macro_news)
    confirmation_read = plain_confirmation_read(item, brief, opportunity, rejection)
    return "\n\n".join(part for part in (catalyst_read, confirmation_read) if part)


def plain_setup_read(item: Analysis) -> str:
    notes = " ".join((item.setup_notes or item.notes)[:5]).lower()
    direction = item.setup_direction or "TRADE"
    if direction == "CALL":
        if "dip" in notes or "oversold" in notes or "support" in notes:
            return "price has pulled into an area where buyers may try to defend it, so the opportunity is a rebound attempt rather than a chase. "
        if "breakout" in notes or "reclaim" in notes:
            return "price is trying to reclaim strength, so the opportunity is a continuation attempt if buyers can hold control. "
        return "the stock has enough upside structure to watch, but it still needs a cleaner entry before I would trust it. "
    if "spike" in notes or "runup" in notes or "resistance" in notes or "rejection" in notes:
        return "price has already made a sharp move into an area where sellers may start fading it, so the opportunity is a controlled pullback attempt. "
    if "breakdown" in notes or "weak" in notes:
        return "price is showing weakness that could continue if buyers fail to reclaim control. "
    return "the stock has enough downside structure to watch, but it still needs confirmation before I would trust it. "


def plain_catalyst_preview(item: Analysis, combined: list[NewsItem], macro_news: list[NewsItem]) -> str:
    direction = item.setup_direction or "TRADE"
    lead = clean_headline(combined[0].title) if combined else ""
    macro_warning = oil_shock_trade_warning(item)
    if not combined:
        base = (
            "I did not find a strong fresh news reason behind this one. That does not automatically make it bad, but it means I would lean more heavily on price action and volume confirmation before trusting the trade."
        )
    else:
        base = (
            f"The useful outside support is this: {lead}. "
            f"My read is that this gives traders something to react to, but I still would not treat the headline as enough by itself."
        )
    if macro_warning:
        if direction == "CALL" and SYMBOL_SECTORS.get(item.symbol.upper()) != "energy":
            base += " Macro alert: oil/geopolitical risk is elevated, so ordinary calls need stronger confirmation than usual."
        elif direction == "CALL":
            base += " Macro alert: the backdrop can help energy calls, but only if the stock confirms instead of opening extended and fading."
        elif direction == "PUT":
            base += " Macro alert: the risk-off backdrop makes the put idea easier to justify if the stock starts rejecting higher prices."
    return base


def plain_confirmation_read(
    item: Analysis,
    brief: TradeBrief | None,
    opportunity: OptionsOpportunityScore,
    rejection: OpportunityRejection,
) -> str:
    direction = item.setup_direction or "TRADE"
    option_side = "calls" if opportunity.call_score >= opportunity.put_score else "puts"
    if brief is None:
        return "The missing piece is confirmation. I would not act on this until the entry plan and option contract are clear."
    trigger = preview_level_text(item, brief.confirmation_level, "the entry trigger")
    invalidation = format_price(brief.invalidation)
    if rejection.action == "NO_TRADE":
        quality = "The stock may be worth watching, but the current contract/risk setup is not clean enough yet."
    elif rejection.action == "ALERT":
        quality = "The setup is close enough to monitor, but I would still wait for the chart to confirm before entering."
    else:
        quality = "The setup is still in watch mode until the next move proves buyers or sellers are actually in control."
    side_note = ""
    if option_side.rstrip("s").upper() != direction:
        side_note = " Options data is not fully lined up with the trade direction yet, so I would be extra selective with the contract."
    return (
        f"What supports the thesis is simple: the news gives the ticker attention, and the chart has a possible {direction.lower()} path if price confirms around {trigger}. "
        f"What would weaken it is just as important: if price loses or reclaims the wrong side of {invalidation}, the idea no longer has the same edge. "
        f"{quality}{side_note}"
    )


def preview_level_text(item: Analysis, level: float | None, fallback: str) -> str:
    if level is None or item.price <= 0:
        return fallback
    if level < item.price * 0.55 or level > item.price * 1.45:
        return fallback
    return format_price(level)


def full_trade_detail_panel(rank: int, item: Analysis) -> str:
    option = item.option
    brief = item.trade_brief
    grade = brief.setup_grade if brief else score_grade(rank_score(item, "trade"))
    pattern = brief.pattern if brief else infer_pattern(item)[0]
    status, _status_detail = entry_status(item, brief)
    exp = option.expiration.isoformat() if option else "-"
    return f"""<section class="setup-details">
  <div class="vital-grid">
    {detail_cell("Grade", grade)}
    {detail_cell("Entry Status", status)}
    {detail_cell("Price", f"${item.price:.2f}")}
    {detail_cell("Recommended Exp", exp)}
    {detail_cell("Pattern Forming", pattern)}
  </div>
  {themed_left_panels(item)}
</section>"""


def detail_article(rank: int, item: Analysis) -> str:
    direction = item.setup_direction or "-"
    direction_class = direction.lower()
    company_name = display_company_name(item.symbol, item.name)
    brief = item.trade_brief
    status, _status_detail = entry_status(item, brief)
    symbol_id = detail_symbol_id(item)
    return f"""<article class="detail-page" id="{html.escape(symbol_id)}" data-symbol="{html.escape(symbol_id)}">
    <header class="hero">
      <div>
        <div class="symbol">{html.escape(item.symbol)}</div>
        <div class="company">{html.escape(company_name)}</div>
      </div>
      <div class="direction {html.escape(direction_class)}">{html.escape(direction)}</div>
    </header>
    <section class="status-card">
      <div class="status-label">Current Status</div>
      <div class="status-value">{html.escape(status)}</div>
    </section>
    <section class="section-grid">
      {full_trade_detail_panel(rank, item)}
      {secondary_analysis_html(item)}
      {trade_brief_html(item)}
    </section>
  </article>"""


def recommendation_class(brief: TradeBrief | None) -> str:
    if brief is None:
        return "watch"
    if brief.final_recommendation.startswith("DO NOT"):
        return "reject"
    if brief.final_recommendation.startswith("Actionable"):
        return "action"
    return "watch"


def themed_left_panels(item: Analysis) -> str:
    brief = item.trade_brief
    entry = item.entry_plan or "-"
    if brief is None:
        return f"""<div class="theme-stack">
  {theme_panel("Entry Plan", entry)}
  {theme_panel("Trader Judgment", "Full trader judgment is unavailable until the trade brief is built.")}
</div>"""

    stance = analyst_stance(item, brief)
    trader = trader_judgment_text(item, brief)
    catalyst = analyst_catalyst_opinion(item)
    option_risk = analyst_option_critique(item, brief)
    technical = technical_context_text(item, brief)
    opportunity = options_opportunity_text(item)
    events = event_intelligence_text(item)
    rejection = rejection_engine_text(item)
    execution = analyst_execution_opinion(item, brief)
    status, status_detail = entry_status(item, brief)
    entry_text = f"Entry status: {status}. {status_detail}\n\n{entry}\n\n{execution}"
    trader_text = f"Analyst stance: {stance}\n\n{trader}"
    return f"""<div class="theme-stack">
  {theme_panel("Entry Plan", entry_text)}
  {theme_panel("Trader Judgment", trader_text)}
  {theme_panel("Options Score", opportunity)}
  {theme_panel("Event Intelligence", events)}
  {theme_panel("Rejection Engine", rejection)}
  {theme_panel("Catalyst / Macro", catalyst)}
  {theme_panel("Option / Risk", option_risk)}
  {theme_panel("Technical Context", technical)}
</div>"""


def theme_panel(title: str, text: str, open_panel: bool = False) -> str:
    open_attr = " open" if open_panel else ""
    return f"""<details class="theme-panel"{open_attr}>
    <summary>{html.escape(title)}</summary>
    <div class="theme-body">{paragraph_html(text)}</div>
  </details>"""


def compact_list(label: str, values: list[str]) -> str:
    if not values:
        return f"{label}: none flagged."
    return f"{label}: " + "; ".join(values[:5]) + "."


def options_opportunity_text(item: Analysis) -> str:
    score = item.options_opportunity or build_options_opportunity_score(item)
    preferred = "CALL" if score.call_score >= score.put_score else "PUT"
    return (
        f"{score.summary}\n\n"
        f"- Preferred side: {preferred}\n"
        f"- Call score: {score.call_score:.0f}/100\n"
        f"- Put score: {score.put_score:.0f}/100\n"
        f"- Confidence: {score.confidence:.0f}/100\n\n"
        f"{compact_list('Bullish evidence', score.bullish_factors)}\n\n"
        f"{compact_list('Bearish evidence', score.bearish_factors)}\n\n"
        f"{compact_list('Risk factors', score.risk_factors)}\n\n"
        f"{compact_list('Missing institutional data', score.missing_data)}"
    )


def event_intelligence_text(item: Analysis) -> str:
    events = item.normalized_events if item.normalized_events is not None else normalize_events_for_item(item)
    if not events:
        return "No normalized catalyst event was available after filtering. Atlas should treat this as a technical setup only until a credible event appears."
    lines = []
    for event in events[:4]:
        path = " -> ".join(event.transmission_path)
        lines.append(
            f"- {event.event_type} / {event.direction}: {event.headline} "
            f"(confidence {event.confidence:.0f}, novelty {event.novelty_score:.0f}, urgency {event.urgency_score:.0f}). "
            f"Transmission: {path}"
        )
    return "\n".join(lines)


def rejection_engine_text(item: Analysis) -> str:
    rejection = item.opportunity_rejection if item.opportunity_rejection is not None else opportunity_rejection_engine(item)
    edge = format_pct(rejection.estimated_edge_pct) if rejection.estimated_edge_pct is not None else "-"
    expected = format_pct(rejection.expected_move_pct) if rejection.expected_move_pct is not None else "-"
    implied = format_pct(rejection.implied_move_pct) if rejection.implied_move_pct is not None else "-"
    reasons = "\n".join(f"- {reason}" for reason in rejection.reasons[:7])
    return (
        f"Action: {rejection.action}\n\n"
        f"- Expected move: {expected}\n"
        f"- Current implied move: {implied}\n"
        f"- Estimated edge: {edge}\n\n"
        f"{reasons}"
    )


def technical_context_text(item: Analysis, brief: TradeBrief) -> str:
    evidence = "; ".join((item.setup_notes or item.notes)[:5]) or "No clean setup evidence available."
    supporting = ", ".join(brief.timeframe_supporting[:4])
    opposing = ", ".join(brief.timeframe_opposing[:4]) if brief.timeframe_opposing else "No major opposing timeframe from available data."
    levels = (
        f"Support/resistance read: {brief.support_resistance} "
        f"Target 1 is {format_price(brief.target_1)}, Target 2 is {format_price(brief.target_2)}, "
        f"Target 3 is {format_price(brief.target_3)}, and invalidation is near {format_price(brief.invalidation)}."
    )
    return (
        f"Pattern/structure: {brief.pattern}. {brief.market_structure}\n\n"
        f"Key evidence: {evidence}\n\n"
        f"Supporting timeframes: {supporting}. Opposing timeframes: {opposing}\n\n"
        f"{levels}"
    )


def secondary_analysis_html(item: Analysis) -> str:
    return f"""<details class="secondary-analysis">
  <summary>Trade details and rationale</summary>
    <div class="secondary-body">
    <div class="rationale"><strong>Professional Analyst Read</strong>{paragraph_html(professional_trade_rationale(item))}</div>
    <div class="signals"><strong>Key setup evidence:</strong> {html.escape('; '.join((item.setup_notes or item.notes)[:4]) or 'No clean setup evidence available')}</div>
  </div>
</details>"""


def paragraph_html(text: str) -> str:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    html_parts: list[str] = []
    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if lines and all(line.startswith("- ") for line in lines):
            items = "".join(f"<li>{html.escape(line[2:].strip())}</li>" for line in lines)
            html_parts.append(f"<ul>{items}</ul>")
        else:
            html_parts.append(f"<p>{html.escape(paragraph)}</p>")
    return "".join(html_parts)


def real_money_trader_judgment(item: Analysis, brief: TradeBrief | None) -> dict[str, object]:
    if brief is None:
        return {
            "score": 35.0,
            "verdict": "Pass until the full trade brief is available",
            "veto": True,
            "reasons": ["The trade brief is missing, so the risk cannot be sized cleanly."],
        }
    score = 100.0
    reasons: list[str] = []
    veto = False
    direction = item.setup_direction or "CALL"
    sector = SYMBOL_SECTORS.get(item.symbol.upper(), "")
    spread = option_spread_pct(item.option)
    shock = macro_oil_shock(item.macro_news or [])
    contract_score, _contract_missing, contract_risks = option_chain_quality(item.option, item)

    if contract_score < 45:
        score -= 18
        reasons.append("The stock setup may be interesting, but the selected option contract quality is poor.")
    elif contract_score < 60:
        score -= 8
        reasons.append("The selected option contract is only average quality; fills and theta need extra care.")
    for risk in contract_risks[:2]:
        if risk not in reasons:
            reasons.append(risk)

    if shock.get("active") and direction == "CALL" and sector != "energy":
        score -= 35
        reasons.append("The trade is a normal CALL fighting an active oil/geopolitical risk-off tape.")
        if brief.setup_grade not in {"A+", "A"} or (item.catalyst_score or 0.0) < 76:
            veto = True
    if shock.get("active") and direction == "PUT" and sector != "energy":
        score += 6
        reasons.append("The macro tape gives this non-energy PUT a cleaner risk-off backdrop.")
    if shock.get("active") and direction == "PUT" and sector == "energy":
        score -= 25
        reasons.append("An energy PUT is fighting crude-supply risk unless oil fades first.")
        veto = True

    if brief.risk_reward is None:
        score -= 18
        reasons.append("Risk/reward is not defined tightly enough for a real-money entry.")
    elif brief.risk_reward < 0.6:
        score -= 30
        reasons.append("Risk/reward is extremely poor; the trade needs a much better entry.")
    elif brief.risk_reward < 1.0:
        score -= 22
        reasons.append("Risk/reward is weak enough that I would not chase it.")
    elif brief.risk_reward < 2.0:
        score -= 10
        reasons.append("Risk/reward is below the preferred 2:1 threshold.")

    if spread is not None and spread > 0.35:
        score -= 20
        reasons.append("The option spread is wide, which makes the real fill quality questionable.")
    elif spread is not None and spread > 0.20:
        score -= 8
        reasons.append("The option spread is usable but requires a patient limit order.")
    if item.option and item.option.estimated:
        score -= 18
        reasons.append("The contract is estimated, so I would verify the option chain before trusting the setup.")

    if item.catalyst_score is not None and item.catalyst_score < 60:
        score -= 16
        reasons.append("Catalyst support is not strong enough to carry a weak entry.")
    if item.volume_ratio is not None and item.volume_ratio < 1.0:
        score -= 10
        reasons.append("Volume confirmation is light, so follow-through is less trustworthy.")
    if len(brief.timeframe_opposing) >= 2:
        score -= 10
        reasons.append("Multiple higher/lower timeframes are fighting the trade.")

    if direction == "CALL" and item.return_5d is not None and item.return_5d > 0.08 and item.rsi is not None and item.rsi > 70:
        score -= 18
        reasons.append("The CALL risks becoming a chase because price is already extended short term.")
    if direction == "PUT" and item.return_5d is not None and item.return_5d < -0.08 and item.rsi is not None and item.rsi < 30:
        score -= 18
        reasons.append("The PUT risks chasing weakness after a stretched selloff.")

    score = clamp(score)
    if score < 45:
        veto = True
    if veto:
        verdict = "Real-money veto"
    elif score >= 78:
        verdict = "Real-money acceptable on trigger"
    elif score >= 62:
        verdict = "Respectable but size small"
    else:
        verdict = "Watch only until quality improves"
    if not reasons:
        reasons.append("No major real-money veto fired; the trade still needs the listed trigger.")
    return {"score": round(score, 1), "verdict": verdict, "veto": veto, "reasons": reasons}


def trader_judgment_text(item: Analysis, brief: TradeBrief | None) -> str:
    judgment = real_money_trader_judgment(item, brief)
    reasons = judgment.get("reasons") or []
    reason_text = " ".join(str(reason) for reason in list(reasons)[:3])
    return f"{judgment['verdict']} ({float(judgment['score']):.0f}/100). {reason_text}"


def is_final_trade_candidate(item: Analysis) -> bool:
    brief = item.trade_brief
    if brief is None:
        return False
    decision = trade_decision(item, brief)
    return decision.tier == "Ready for Entry"


def is_report_candidate(item: Analysis) -> bool:
    brief = item.trade_brief
    if brief is None:
        return False
    decision = trade_decision(item, brief)
    return decision.tier in {"Live Watchlist", "Entry Candidate", "Ready for Entry"}


def trade_decision(item: Analysis, brief: TradeBrief | None) -> TradeDecision:
    if brief is None:
        return TradeDecision(
            tier="Pass",
            status="No trade",
            stance="Pass for now",
            notify=False,
            trader_score=35.0,
            contract_score=30.0,
            catalyst_score=0.0,
            reasons=["Trade brief is unavailable."],
            blockers=["Missing trade brief"],
        )
    rejection = item.opportunity_rejection if item.opportunity_rejection is not None else opportunity_rejection_engine(item)
    judgment = real_money_trader_judgment(item, brief)
    trader_score = float(judgment.get("score") or 0.0)
    contract_score, _contract_missing, contract_risks = option_chain_quality(item.option, item)
    catalyst = float(item.catalyst_score if item.catalyst_score is not None else 50.0)
    direction = item.setup_direction or "CALL"
    price = item.price
    invalidation = brief.invalidation
    blockers: list[str] = []
    reasons: list[str] = []

    if rejection.action == "NO_TRADE":
        blockers.extend(reason for reason in rejection.reasons if reason.startswith("NO_TRADE"))
    if bool(judgment.get("veto")):
        blockers.append("Real-money quality screen vetoed this setup")
    if invalidation is not None:
        if direction == "CALL" and price <= invalidation:
            blockers.append(f"Price is at or below invalidation near {format_price(invalidation)}")
        if direction == "PUT" and price >= invalidation:
            blockers.append(f"Price is at or above invalidation near {format_price(invalidation)}")

    if blockers:
        return TradeDecision(
            tier="Pass",
            status="No trade",
            stance="Pass for now",
            notify=False,
            trader_score=trader_score,
            contract_score=contract_score,
            catalyst_score=catalyst,
            reasons=list(dict.fromkeys(blockers + list(judgment.get("reasons") or [])[:2])),
            blockers=list(dict.fromkeys(blockers)),
        )

    spread = option_spread_pct(item.option)
    intraday = trend_label(item.intraday_closes or [], 8, 20)
    wanted = "bullish" if direction == "CALL" else "bearish"
    intraday_ok = intraday == wanted
    volume_ok = item.volume_ratio is not None and item.volume_ratio >= 1.1
    near_zone = price_is_near_starter_zone(item)
    rr_ok = brief.risk_reward is not None and brief.risk_reward >= 1.0
    rr_strong = brief.risk_reward is not None and brief.risk_reward >= 1.5
    contract_clean = contract_score >= 50 and not (item.option and item.option.estimated) and not (spread is not None and spread > 0.40)
    catalyst_ok = catalyst >= 58
    catalyst_strong = catalyst >= 62
    setup_good = brief.setup_grade in {"A+", "A", "B"} or trader_score >= 62
    timing_ok = near_zone or intraday_ok or volume_ok
    confirmation_ok = intraday_ok or volume_ok
    quality_points = sum(
        (
            trader_score >= 60,
            contract_score >= 55,
            catalyst_ok,
            rr_ok,
            setup_good,
            near_zone,
            confirmation_ok,
            rr_strong,
            catalyst_strong,
        )
    )

    if not contract_clean:
        reasons.extend(contract_risks[:2] or ["Contract is usable only with extra fill discipline."])
    if not catalyst_ok:
        reasons.append("Catalyst support is not strong enough for an entry-level trade.")
    if not rr_ok:
        reasons.append("Risk/reward still needs a cleaner entry.")
    if not near_zone:
        reasons.append("Price is not close enough to the preferred inflection zone.")
    if not confirmation_ok:
        reasons.append("Waiting for either 15m direction or volume to confirm.")

    ready = (
        trader_score >= 60
        and contract_clean
        and catalyst_ok
        and rr_ok
        and timing_ok
        and quality_points >= 5
    )
    if ready:
        return TradeDecision(
            tier="Ready for Entry",
            status="Ready for Entry",
            stance="Ready for Entry",
            notify=True,
            trader_score=trader_score,
            contract_score=contract_score,
            catalyst_score=catalyst,
            reasons=["Strong enough catalyst, contract, risk/reward, and timing alignment for an actionable entry."],
            blockers=[],
        )

    entry_candidate = (
        trader_score >= 58
        and contract_score >= 45
        and catalyst_ok
        and rr_ok
        and (near_zone or rr_strong or intraday_ok or volume_ok)
    )
    if entry_candidate:
        return TradeDecision(
            tier="Entry Candidate",
            status="Entry Candidate",
            stance="Entry Candidate",
            notify=False,
            trader_score=trader_score,
            contract_score=contract_score,
            catalyst_score=catalyst,
            reasons=list(dict.fromkeys(reasons or ["Trade is close, but not ready enough to notify."])),
            blockers=[],
        )

    live_watchlist = trader_score >= 45 or catalyst >= 55 or brief.confidence_score >= 55
    if live_watchlist:
        return TradeDecision(
            tier="Live Watchlist",
            status="Live Watchlist",
            stance="Live Watchlist",
            notify=False,
            trader_score=trader_score,
            contract_score=contract_score,
            catalyst_score=catalyst,
            reasons=list(dict.fromkeys(reasons or ["Credible developing setup, but not close enough for an entry alert."])),
            blockers=[],
        )

    return TradeDecision(
        tier="Pass",
        status="No trade",
        stance="Pass for now",
        notify=False,
        trader_score=trader_score,
        contract_score=contract_score,
        catalyst_score=catalyst,
        reasons=list(dict.fromkeys(reasons or ["Setup quality is too weak for the live list."])),
        blockers=[],
    )


def entry_status(item: Analysis, brief: TradeBrief | None) -> tuple[str, str]:
    decision = trade_decision(item, brief)
    if decision.status == "Ready for Entry":
        return decision.status, "Entry-level conditions are aligned enough to notify."
    if decision.status == "Entry Candidate":
        return decision.status, "Trade is close, but one or more timing/quality checks are still missing."
    if decision.status == "Live Watchlist":
        return decision.status, "Credible developing setup; monitor it, but do not enter yet."
    if decision.blockers:
        return "No trade", "; ".join(decision.blockers[:2])
    return "No trade", decision.reasons[0] if decision.reasons else "Current trade quality is too weak."


def price_is_near_starter_zone(item: Analysis) -> bool:
    _text, support, resistance = support_resistance_text(item)
    atr = average_true_range(item.chart_highs or [], item.chart_lows or [], item.chart_closes or [])
    buffer = atr * 0.75 if atr else item.price * 0.015
    direction = item.setup_direction or "CALL"
    if direction == "CALL" and support is not None:
        return abs(item.price - support) <= buffer or item.price <= support + buffer
    if direction == "PUT" and resistance is not None:
        return abs(item.price - resistance) <= buffer or item.price >= resistance - buffer
    return False


def analyst_stance(item: Analysis, brief: TradeBrief | None) -> str:
    decision = trade_decision(item, brief)
    if decision.status in {"Ready for Entry", "Entry Candidate", "Live Watchlist", "No trade"}:
        if decision.status == "No trade":
            judgment = real_money_trader_judgment(item, brief)
            if judgment.get("veto"):
                return f"Pass for now - {judgment['verdict']}"
            return "Pass for now"
        return decision.status
    if brief is None:
        return "Watch only"
    judgment = real_money_trader_judgment(item, brief)
    if judgment.get("veto"):
        return f"Pass for now - {judgment['verdict']}"
    spread = option_spread_pct(item.option)
    weak_catalyst = item.catalyst_score is not None and item.catalyst_score < 60
    weak_rr = brief.risk_reward is None or brief.risk_reward < 2
    very_weak_rr = brief.risk_reward is None or brief.risk_reward < 0.6
    wide_spread = spread is not None and spread > 0.35
    shock = macro_oil_shock(item.macro_news or [])
    sector = SYMBOL_SECTORS.get(item.symbol.upper(), "")
    if shock.get("active") and item.setup_direction == "CALL" and sector != "energy":
        if brief.setup_grade not in {"A+", "A"} or (item.catalyst_score or 0.0) < 76:
            return "Pass for now - macro risk is fighting normal calls"
        return "Watch only - macro risk is fighting normal calls"
    if shock.get("active") and item.setup_direction == "PUT" and sector != "energy" and not very_weak_rr:
        if not weak_catalyst and not wide_spread:
            return "Actionable on trigger"
    if very_weak_rr and (weak_catalyst or wide_spread):
        return "Pass for now"
    if brief.setup_grade in {"A+", "A"} and not brief.avoid_reasons and not weak_catalyst:
        return "Actionable on trigger"
    if wide_spread:
        return "Watch only - option spread is the issue"
    if weak_catalyst:
        return "Watch only - catalyst support is not strong enough"
    if weak_rr:
        return "Early watch - needs a better entry"
    if brief.setup_grade in {"Watch", "Wait"}:
        return "Wait for confirmation"
    return "Conditional setup"


def telegram_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def send_telegram_message(message: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return 200 <= response.status < 300


def alert_state_path() -> Path:
    configured = os.environ.get("STOCK_ANALYST_ALERT_STATE")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / ".stock_analyst_alerts.json"


def load_alert_state() -> dict[str, Any]:
    path = alert_state_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"sent": [], "observed": {}, "heartbeat_dates": [], "active_positions": {}}
    if not isinstance(payload, dict):
        payload = {"sent": payload, "observed": {}, "heartbeat_dates": [], "active_positions": {}}
    sent = payload.get("sent") or []
    observed = payload.get("observed") or {}
    heartbeat_dates = payload.get("heartbeat_dates") or []
    active_positions = payload.get("active_positions") or {}
    if not isinstance(observed, dict):
        observed = {}
    if not isinstance(active_positions, dict):
        active_positions = {}
    return {
        "sent": [str(key) for key in sent if str(key).strip()],
        "observed": {str(key): value for key, value in observed.items() if isinstance(value, dict)},
        "heartbeat_dates": [str(value) for value in heartbeat_dates if str(value).strip()],
        "active_positions": {str(key): value for key, value in active_positions.items() if isinstance(value, dict)},
    }


def save_alert_state(state: dict[str, Any]) -> None:
    path = alert_state_path()
    sent = [str(key) for key in state.get("sent", []) if str(key).strip()]
    observed = state.get("observed") or {}
    heartbeat_dates = [str(value) for value in state.get("heartbeat_dates", []) if str(value).strip()]
    active_positions = state.get("active_positions") or {}
    path.write_text(
        json.dumps(
            {
                "sent": sorted(set(sent))[-500:],
                "observed": observed if isinstance(observed, dict) else {},
                "heartbeat_dates": sorted(set(heartbeat_dates))[-30:],
                "active_positions": active_positions if isinstance(active_positions, dict) else {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def report_public_url(output: Path | str) -> str:
    base_url = os.environ.get("STOCK_ANALYST_PUBLIC_URL", "").strip().rstrip("/")
    report_name = Path(output).name
    if base_url:
        return f"{base_url}/{report_name}"
    return report_name


def alert_key(item: Analysis, stance: str) -> str:
    today = dt.datetime.now().astimezone().date().isoformat()
    return f"{today}:report-add:{item.symbol}:{item.setup_direction or '-'}"


def alert_event_key(event: AlertEvent) -> str:
    today = dt.datetime.now().astimezone().date().isoformat()
    direction = event.direction or "-"
    label = alert_notification_label(event.stance, event.status)
    if event.kind == "position":
        bucket = pct_change_bucket(event.percent_change or 0.0)
        return f"{today}:position:{event.position_key or event.symbol}:{bucket}"
    if event.kind == "entry":
        return f"{today}:entry:{event.symbol}:{direction}:{event.status or label}"
    if event.kind == "removed":
        return f"{today}:removed:{event.symbol}:{direction}"
    return f"{today}:report-add:{event.symbol}:{direction}"


def observed_alert_key(item: Analysis) -> str:
    return f"{item.symbol}:{item.setup_direction or '-'}"


@dataclass
class AlertEvent:
    kind: str
    symbol: str
    direction: str
    stance: str = ""
    status: str = ""
    item: Analysis | None = None
    previous: dict[str, Any] | None = None
    position_key: str = ""
    percent_change: float | None = None


def is_watch_or_wait_state(stance: str, status: str) -> bool:
    return (
        stance in {"Live Watchlist", "Entry Candidate"}
        or status in {"Live Watchlist", "Entry Candidate"}
        or stance.startswith("Watch")
        or stance.startswith("Wait")
        or stance.startswith("Early watch")
        or stance.startswith("Conditional")
        or status in {"Watch only", "Trigger forming"}
    )


def is_enter_now_state(stance: str, status: str) -> bool:
    if status in {"Ready for Entry", "Confirmed entry"}:
        return True
    return False


def is_high_confidence_entry_alert(item: Analysis, stance: str, status: str) -> bool:
    if status != "Ready for Entry":
        return False
    if stance != "Ready for Entry":
        return False
    brief = item.trade_brief
    if brief is None:
        return False
    judgment = real_money_trader_judgment(item, brief)
    min_score = float(os.environ.get("STOCK_ANALYST_READY_ALERT_MIN_SCORE", "60") or "60")
    return not bool(judgment.get("veto")) and float(judgment.get("score") or 0.0) >= min_score


def current_alert_observations(results: list[Analysis]) -> dict[str, dict[str, str]]:
    observations: dict[str, dict[str, str]] = {}
    for item in results:
        brief = item.trade_brief
        stance = analyst_stance(item, brief)
        status, _detail = entry_status(item, brief)
        observations[observed_alert_key(item)] = {
            "symbol": item.symbol,
            "direction": item.setup_direction or "",
            "stance": stance,
            "status": status,
            "updated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    return observations


def alert_candidates_from_transitions(
    results: list[Analysis],
    previous: dict[str, dict[str, str]],
) -> list[AlertEvent]:
    candidates: list[AlertEvent] = []
    for item in results:
        brief = item.trade_brief
        stance = analyst_stance(item, brief)
        status, _detail = entry_status(item, brief)
        key = observed_alert_key(item)
        prior = previous.get(key)
        prior_status = str((prior or {}).get("status") or "")
        prior_stance = str((prior or {}).get("stance") or "")
        if (
            is_high_confidence_entry_alert(item, stance, status)
            and not is_enter_now_state(prior_stance, prior_status)
        ):
            candidates.append(
                AlertEvent(
                    kind="entry",
                    symbol=item.symbol,
                    direction=item.setup_direction or "",
                    stance=stance,
                    status=status,
                    item=item,
                    previous=prior,
                )
            )
    limit = max(1, int(os.environ.get("STOCK_ANALYST_ALERT_LIMIT", "5") or "5"))
    return candidates[:limit]


def alert_notification_label(stance: str, status: str) -> str:
    if status in {"Ready for Entry", "Confirmed entry"}:
        return "Enter now"
    if status == "Entry Candidate":
        return "Entry Candidate"
    if status == "Live Watchlist":
        return "Live Watchlist"
    if stance.startswith("Watch"):
        return "Watch only"
    if stance.startswith("Wait"):
        return "Wait"
    if stance.startswith("Early watch"):
        return "Early watch"
    if stance.startswith("Actionable"):
        return "Actionable on trigger"
    if status:
        return status
    return stance or "Added"


def format_entry_expiration(item: Analysis) -> str:
    if item.option is None:
        return "exp TBD"
    return item.option.expiration.isoformat()


def format_entry_strike(item: Analysis) -> str:
    side = item.setup_direction or (item.option.side if item.option else "OPTION")
    if item.option is None:
        return f"strike TBD {side}"
    strike = f"{item.option.strike:g}"
    return f"{strike} {side}"


def format_entry_tp_sl(item: Analysis) -> str:
    goals = [goal for _label, _target, goal in target_profit_levels(item)]
    tp_text = ", ".join(f"+{goal}%" for goal in goals[:3]) if goals else "+20%"
    stop_pct = os.environ.get("STOCK_ANALYST_ALERT_STOP_PCT", "25").strip() or "25"
    try:
        stop_value = abs(float(stop_pct))
        stop_text = f"-{stop_value:g}%"
    except ValueError:
        stop_text = "-25%"
    return f"TP {tp_text} & SL {stop_text}"


def position_key_from_item(item: Analysis) -> str:
    direction = item.setup_direction or (item.option.side if item.option else "-")
    contract = item.option.contract_symbol if item.option else ""
    if contract:
        return f"{item.symbol}:{direction}:{contract}"
    return f"{item.symbol}:{direction}"


def build_active_position(item: Analysis) -> dict[str, Any] | None:
    entry_price = option_mid_price(item.option)
    if item.option is None or entry_price is None or entry_price <= 0:
        return None
    return {
        "symbol": item.symbol,
        "direction": item.setup_direction or item.option.side,
        "contract": item.option.contract_symbol,
        "expiration": item.option.expiration.isoformat(),
        "strike": item.option.strike,
        "side": item.option.side,
        "entry_option_price": entry_price,
        "opened_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "last_alert_bucket": 0,
        "closed": False,
    }


def pct_change_bucket(percent_change: float) -> int:
    absolute = abs(percent_change)
    if absolute < 10:
        return 0
    bucket = int(math.floor(absolute / 5.0) * 5)
    return bucket if percent_change > 0 else -bucket


def position_update_action(event: AlertEvent) -> str:
    pct = event.percent_change or 0.0
    if pct <= -20:
        return "recommended action: cut the position"
    if pct <= -15:
        return "recommended action: cut if it does not reclaim quickly"
    if pct <= -10:
        return "recommended action: watch closely; cut on another weak candle"
    if pct >= 25:
        status = event.status
        if status in {"Ready for Entry", "Confirmed entry", "Entry Candidate", "Starter entry active", "Trigger forming"}:
            return "recommended action: take partial profit and hold a runner"
        return "recommended action: take profit"
    if pct >= 20:
        return "recommended action: take profit on part; hold only if momentum stays strong"
    return "recommended action: hold for the 20-25% target unless momentum fades"


def should_close_tracked_position(event: AlertEvent) -> bool:
    action = position_update_action(event)
    return "cut the position" in action or action.endswith("take profit")


def position_events_from_active(
    results: list[Analysis],
    active_positions: dict[str, dict[str, Any]],
) -> list[AlertEvent]:
    by_symbol_direction = {
        observed_alert_key(item): item
        for item in results
    }
    events: list[AlertEvent] = []
    for key, position in active_positions.items():
        if position.get("closed"):
            continue
        symbol = str(position.get("symbol") or "").upper()
        direction = str(position.get("direction") or "")
        item = by_symbol_direction.get(f"{symbol}:{direction}")
        if item is None:
            continue
        current_price = option_mid_price(item.option)
        entry_price = float(position.get("entry_option_price") or 0.0)
        if current_price is None or current_price <= 0 or entry_price <= 0:
            continue
        pct = ((current_price - entry_price) / entry_price) * 100
        bucket = pct_change_bucket(pct)
        last_bucket = int(position.get("last_alert_bucket") or 0)
        if bucket == 0 or bucket == last_bucket:
            continue
        stance = analyst_stance(item, item.trade_brief)
        status, _detail = entry_status(item, item.trade_brief)
        events.append(
            AlertEvent(
                kind="position",
                symbol=symbol,
                direction=direction,
                stance=stance,
                status=status,
                item=item,
                previous=position,
                position_key=key,
                percent_change=pct,
            )
        )
    return events


def format_trade_alert(event: AlertEvent, report_url: str = "") -> str:
    if event.kind == "position":
        bucket = abs(pct_change_bucket(event.percent_change or 0.0))
        direction = "gained" if (event.percent_change or 0.0) > 0 else "lost"
        return f"Your {event.symbol} contract has {direction} more than {bucket}% ({position_update_action(event)})"
    if event.kind == "entry" and event.item is not None:
        return (
            f"{event.symbol} ready for entry "
            f"({format_entry_expiration(event.item)}) "
            f"({format_entry_strike(event.item)}) "
            f"({format_entry_tp_sl(event.item)})"
        )
    return ""


def maybe_send_trade_alerts(results: list[Analysis], output: Path | str) -> int:
    if not telegram_configured():
        return 0
    state = load_alert_state()
    sent_keys = set(str(key) for key in state.get("sent", []))
    previous = state.get("observed") or {}
    active_positions = state.get("active_positions") or {}
    if not isinstance(active_positions, dict):
        active_positions = {}
    report_url = report_public_url(output)
    sent_count = 0
    events = position_events_from_active(results, active_positions) + alert_candidates_from_transitions(results, previous)
    for event in events:
        key = alert_event_key(event)
        if key in sent_keys:
            continue
        try:
            if send_telegram_message(format_trade_alert(event, report_url)):
                sent_keys.add(key)
                sent_count += 1
                if event.kind == "entry" and event.item is not None:
                    position = build_active_position(event.item)
                    if position is not None:
                        active_positions[position_key_from_item(event.item)] = position
                if event.kind == "position" and event.position_key:
                    position = active_positions.get(event.position_key)
                    if isinstance(position, dict):
                        position["last_alert_bucket"] = pct_change_bucket(event.percent_change or 0.0)
                        position["last_alert_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
                        if should_close_tracked_position(event):
                            position["closed"] = True
                            position["closed_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        except Exception as exc:
            print(f"Telegram alert failed for {event.symbol}: {exc}", file=sys.stderr)
    state["sent"] = sorted(sent_keys)
    state["observed"] = current_alert_observations(results)
    state["active_positions"] = active_positions
    save_alert_state(state)
    return sent_count


def send_test_alert() -> bool:
    generated = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return send_telegram_message(
        "Atlas test alert\n"
        f"Time: {generated}\n"
        "If you got this, phone notifications are connected. Atlas will notify when a new ticker is added to the current watchlist."
    )


def sample_trade_alert_item() -> Analysis:
    return Analysis(
        symbol="TEST",
        name="Test Setup",
        price=100.0,
        score=80,
        rating="Candidate",
        momentum_score=75,
        value_score=55,
        risk_score=65,
        yield_score=40,
        return_1y=0.12,
        return_6m=0.06,
        return_3m=0.04,
        volatility=0.25,
        max_drawdown=-0.10,
        sharpe_like=None,
        rsi=55,
        sma_50=98,
        sma_200=92,
        market_cap=None,
        pe=None,
        dividend_yield=None,
        beta=None,
        notes=[],
        news=[],
        setup_direction="CALL",
        option=OptionContract(
            contract_symbol="TEST260629C00105000",
            side="CALL",
            strike=105.0,
            expiration=dt.date(2026, 6, 29),
            bid=2.0,
            ask=2.2,
            last_price=2.1,
            volume=100,
            open_interest=500,
            implied_volatility=0.45,
        ),
    )


def sample_trade_alert_events() -> list[AlertEvent]:
    item = sample_trade_alert_item()
    return [
        AlertEvent(kind="entry", symbol=item.symbol, direction="CALL", stance="Ready for Entry", status="Ready for Entry", item=item),
        AlertEvent(kind="position", symbol=item.symbol, direction="CALL", stance="Ready for Entry", status="Ready for Entry", item=item, position_key="TEST:CALL:TEST260629C00105000", percent_change=22.0),
        AlertEvent(kind="position", symbol=item.symbol, direction="CALL", stance="Live Watchlist", status="Live Watchlist", item=item, position_key="TEST:CALL:TEST260629C00105000", percent_change=-21.0),
    ]


def send_test_trade_alerts() -> tuple[int, list[str]]:
    messages = [format_trade_alert(event) for event in sample_trade_alert_events()]
    sent = 0
    for message in messages:
        if send_telegram_message(message):
            sent += 1
    return sent, messages


SCAN_LOCK = threading.Lock()
MARKET_TIMEZONE = ZoneInfo("America/New_York")
MARKET_SNAPSHOT_CACHE: dict[str, Any] = {"timestamp": 0.0, "value": None}


def market_now(now: dt.datetime | None = None) -> dt.datetime:
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    return current.astimezone(MARKET_TIMEZONE)


def in_market_alert_window(now: dt.datetime | None = None) -> bool:
    current = market_now(now)
    if current.weekday() >= 5:
        return False
    start = current.replace(hour=9, minute=25, second=0, microsecond=0)
    end = current.replace(hour=16, minute=10, second=0, microsecond=0)
    return start <= current <= end


def market_open_heartbeat_due(now: dt.datetime | None = None) -> bool:
    current = market_now(now)
    if current.weekday() >= 5:
        return False
    start = current.replace(hour=9, minute=30, second=0, microsecond=0)
    end = current.replace(hour=9, minute=45, second=0, microsecond=0)
    return start <= current <= end


def send_market_open_heartbeat(now: dt.datetime | None = None) -> bool:
    if not telegram_configured() or not market_open_heartbeat_due(now):
        return False
    current = market_now(now)
    today = current.date().isoformat()
    state = load_alert_state()
    sent_dates = set(str(value) for value in state.get("heartbeat_dates", []))
    if today in sent_dates:
        return False
    message = "Atlas online - market scan active"
    try:
        if not send_telegram_message(message):
            return False
    except Exception as exc:
        print(f"Market-open heartbeat failed: {exc}", file=sys.stderr, flush=True)
        return False
    sent_dates.add(today)
    state["heartbeat_dates"] = sorted(sent_dates)
    save_alert_state(state)
    print("Market-open heartbeat sent.", flush=True)
    return True


def auto_scan_minutes() -> int:
    raw_value = os.environ.get("STOCK_ANALYST_AUTO_SCAN_MINUTES", "").strip()
    if not raw_value:
        return 0
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 0


def run_scheduled_scan_once() -> None:
    if not SCAN_LOCK.acquire(blocking=False):
        print("Scheduled scan skipped because another scan is already running.", flush=True)
        return
    try:
        script_path = Path(__file__).resolve()
        command = scanner_command(script_path, "stock_report.html")
        completed = subprocess.run(
            command,
            cwd=script_path.parent,
            capture_output=True,
            text=True,
            timeout=480,
        )
        if completed.returncode == 0:
            print("Scheduled scan finished.", flush=True)
        else:
            error_text = (completed.stderr or completed.stdout or "Scheduled scan failed.").strip().splitlines()
            print(f"Scheduled scan failed: {error_text[-1] if error_text else 'unknown error'}", file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"Scheduled scan failed: {exc}", file=sys.stderr, flush=True)
    finally:
        SCAN_LOCK.release()


def scheduled_scan_loop(minutes: int) -> None:
    while True:
        if in_market_alert_window():
            send_market_open_heartbeat()
            run_scheduled_scan_once()
        time.sleep(max(60, minutes * 60))


def start_scheduled_scanner() -> None:
    minutes = auto_scan_minutes()
    if minutes <= 0:
        return
    thread = threading.Thread(target=scheduled_scan_loop, args=(minutes,), daemon=True)
    thread.start()
    print(f"Automatic market-hours scanner enabled every {minutes} minute(s).", flush=True)


def analyst_catalyst_opinion(item: Analysis) -> str:
    symbol = item.symbol
    score = item.catalyst_score if item.catalyst_score is not None else 50.0
    summary = expanded_news_summary(item)
    if not item.news and not item.macro_news:
        return (
            f"I do not see enough fresh, stock-specific catalyst backing for {symbol} from the connected feeds. "
            "That does not kill the trade by itself, but it means the chart has to do most of the work and I would not pay up just because the ticker looks active."
        )
    if score >= 80:
        judgment = (
            "The catalyst support is real enough to matter. I would treat the news as a legitimate reason traders may keep this name active, "
            "not just background noise or a recycled analyst headline."
        )
    elif score >= 65:
        judgment = (
            "The catalyst support is useful but not dominant. It gives the setup a reason to stay on watch, but it is not strong enough for me to ignore a bad entry."
        )
    else:
        judgment = (
            "The catalyst support is thin or mixed. I would be careful about forcing a trade here because the news is not strong enough to carry the setup on its own."
        )
    return f"{judgment} {summary}"


def analyst_option_critique(item: Analysis, brief: TradeBrief) -> str:
    option = item.option
    parts: list[str] = []
    if option is None:
        parts.append("I do not have a clean live contract attached, so the option side is less dependable than the stock setup.")
    else:
        if option.estimated:
            parts.append("The listed contract is estimated, so I would verify the chain manually before placing anything.")
        spread = option_spread_pct(option)
        if spread is not None:
            if spread > 0.35:
                parts.append("The bid/ask spread is wide, which can turn a good chart read into a poor fill.")
            elif spread > 0.20:
                parts.append("The spread is acceptable but not perfect, so limit orders matter.")
            else:
                parts.append("The option spread looks usable for a short-term long call/put idea.")
        days_to_exp = (option.expiration - dt.datetime.now().astimezone().date()).days
        if days_to_exp <= 10:
            parts.append("Expiration is close, so theta risk is high and the trade needs to work quickly.")
        elif days_to_exp <= 21:
            parts.append("Expiration gives some room, but I would still avoid sitting through dead chop.")
        else:
            parts.append("Expiration gives a more reasonable swing window than a near-dated gamble.")
    if brief.risk_reward is None:
        parts.append("Risk/reward is not fully defined, which lowers my confidence.")
    elif brief.risk_reward < 2:
        parts.append(f"The current risk/reward is only {brief.risk_reward:.2f}:1, so I would wait for a better entry instead of accepting a weak payout profile.")
    else:
        parts.append(f"The current risk/reward is {brief.risk_reward:.2f}:1, which is workable if the trigger confirms.")
    return " ".join(parts)


def analyst_execution_opinion(item: Analysis, brief: TradeBrief) -> str:
    direction = item.setup_direction or "CALL"
    target = format_price(brief.target_1)
    stop = format_price(brief.stop_loss)
    invalidation = format_price(brief.invalidation)
    if direction == "CALL":
        confirmation = "buyers defend the current zone, print a higher low, or reclaim short-term VWAP/structure with volume"
        failure = "price loses the defended zone and cannot quickly reclaim it"
    else:
        confirmation = "sellers reject the bounce, print a lower high, or lose short-term VWAP/structure with volume"
        failure = "price reclaims the rejection zone and starts holding above it"
    return (
        "- Do not chase the open; let the first move show its hand.\n"
        f"- Enter only if {confirmation}.\n"
        f"- First objective: +20% option goal, roughly tied to {target} underlying.\n"
        f"- Risk line: control risk around {stop}; downgrade if {failure} or price trades through {invalidation}."
    )


def professional_trade_rationale(item: Analysis) -> str:
    brief = item.trade_brief
    direction = item.setup_direction or "CALL"
    setup = item.setup_label or "chart setup"
    if brief is None:
        return (
            f"Analyst stance: Watch only. {item.symbol} is on the list as a {direction} idea because the scanner found a {setup}, "
            "but I would not treat it as actionable until the full trade brief, catalyst read, and option structure are available."
        )
    stance = analyst_stance(item, brief)
    supporting = ", ".join(brief.timeframe_supporting[:3])
    opposing = ", ".join(brief.timeframe_opposing[:2]) if brief.timeframe_opposing else "no major opposing timeframe from the available data"
    like = brief.take_reasons[0] if brief.take_reasons else f"The chart has enough structure to keep {item.symbol} on watch."
    dislike = brief.avoid_reasons[0] if brief.avoid_reasons else "The main weakness is still execution risk: a failed trigger or weak follow-through would cancel the idea."
    catalyst_opinion = analyst_catalyst_opinion(item)
    option_critique = analyst_option_critique(item, brief)
    trader_judgment = trader_judgment_text(item, brief)
    execution = analyst_execution_opinion(item, brief)
    if stance.startswith("Pass"):
        opener = (
            f"Analyst stance: {stance}. I would not force {item.symbol} here even though it showed up as a {direction} candidate. "
            "The setup may be interesting, but the current trade quality is not clean enough yet."
        )
    elif stance.startswith("Actionable"):
        opener = (
            f"Analyst stance: {stance}. {item.symbol} is one of the cleaner {direction} ideas on this scan, but it is still trigger-dependent, "
            "not a blind entry."
        )
    elif stance.startswith("Wait"):
        opener = (
            f"Analyst stance: {stance}. {item.symbol} has enough evidence to monitor, but I would make the stock prove the turn or breakdown before committing."
        )
    elif stance.startswith("Early watch"):
        opener = (
            f"Analyst stance: {stance}. {item.symbol} is interesting enough to track, but the entry has to be closer to the inflection zone than a normal confirmation trade."
        )
    else:
        opener = (
            f"Analyst stance: {stance}. {item.symbol} is worth watching as a {direction} swing idea, but I would keep the position plan conditional rather than assuming "
            "the scan result is enough by itself."
        )
    return (
        f"{opener} What I like: {like} What I dislike: {dislike}\n\n"
        f"Catalyst judgment: {catalyst_opinion}\n\n"
        f"Trader judgment: {trader_judgment}\n\n"
        f"Trade criticism: the supporting picture is {supporting}, while the main conflict is {opposing}. {option_critique}\n\n"
        f"Execution plan: {execution}"
    )


def trade_brief_html(item: Analysis) -> str:
    brief = item.trade_brief
    if brief is None:
        return ""
    rec_class = recommendation_class(brief)
    take_items = "".join(f"<li>{html.escape(reason)}</li>" for reason in brief.take_reasons)
    avoid_items = "".join(f"<li>{html.escape(reason)}</li>" for reason in brief.avoid_reasons)
    supporting = ", ".join(brief.timeframe_supporting)
    opposing = ", ".join(brief.timeframe_opposing) if brief.timeframe_opposing else "None from available data"
    rr = f"{brief.risk_reward:.2f}:1" if brief.risk_reward is not None else "-"
    levels = (
        f"Entry zone: current/trigger-based. Stop {format_price(brief.stop_loss)}. "
        f"T1 {format_price(brief.target_1)}, T2 {format_price(brief.target_2)}, T3 {format_price(brief.target_3)}. "
        f"Risk/reward {rr}. Invalidation {format_price(brief.invalidation)}."
    )
    return f"""<div class="trade-brief">
  <div class="brief-title">Full Trade Brief</div>
  <div class="brief-grid">
    <div class="brief-section full recommendation {rec_class}"><strong>Final Recommendation</strong>{html.escape(brief.final_recommendation)}</div>
    <div class="brief-section full"><strong>Trade Thesis</strong>{html.escape(brief.thesis)}</div>
    <div class="brief-section"><strong>Pattern</strong>{html.escape(brief.pattern)}. Status: {html.escape(brief.pattern_status)}. Confirmation: {format_num(brief.confirmation_level)}.</div>
    <div class="brief-section"><strong>Confidence</strong>{html.escape(brief.setup_grade)} setup. Score {brief.confidence_score:.1f}/100. Alignment {brief.alignment_score:.1f}/100.</div>
    <div class="brief-section full"><strong>Market Structure</strong>{html.escape(brief.market_structure)}</div>
    <div class="brief-section"><strong>Timeframes Supporting</strong>{html.escape(supporting)}</div>
    <div class="brief-section"><strong>Timeframes Opposing</strong>{html.escape(opposing)}</div>
    <div class="brief-section full"><strong>Trade Levels</strong>{html.escape(levels)}</div>
    <div class="brief-section"><strong>Indicators</strong>{html.escape(brief.indicator_analysis)}</div>
    <div class="brief-section"><strong>Volume</strong>{html.escape(brief.volume_analysis)}</div>
    <div class="brief-section"><strong>Relative Strength</strong>{html.escape(brief.relative_strength)}</div>
    <div class="brief-section"><strong>Support / Resistance</strong>{html.escape(brief.support_resistance)}</div>
    <div class="brief-section"><strong>Volume Profile</strong>{html.escape(brief.volume_profile)}</div>
    <div class="brief-section"><strong>Liquidity</strong>{html.escape(brief.liquidity_analysis)}</div>
    <div class="brief-section"><strong>Options Flow</strong>{html.escape(brief.options_flow)}</div>
    <div class="brief-section"><strong>Order Flow</strong>{html.escape(brief.order_flow)}</div>
    <div class="brief-section full"><strong>Catalyst Analysis</strong>{html.escape(brief.catalyst_analysis)}</div>
    <div class="brief-section"><strong>Market Environment</strong>{html.escape(brief.market_environment)}</div>
    <div class="brief-section"><strong>Economic Event Risk</strong>{html.escape(brief.event_risk)}</div>
    <div class="brief-section full"><strong>Bull / Base / Bear</strong>{html.escape(brief.bull_case)} {html.escape(brief.base_case)} {html.escape(brief.bear_case)}</div>
    <div class="brief-section"><strong>Reasons To Take</strong><ul>{take_items}</ul></div>
    <div class="brief-section"><strong>Reasons NOT To Take</strong><ul>{avoid_items}</ul></div>
  </div>
</div>"""


def detail_cell(label: str, value: str) -> str:
    return f"""<div class="detail">
  <div class="detail-label">{html.escape(label)}</div>
  <div class="detail-value">{html.escape(value)}</div>
</div>"""


def major_headlines_digest(item: Analysis, limit: int = 3) -> str:
    headlines = select_major_headlines(item, limit)
    if not headlines:
        return '<div class="headline-list"><div class="headline-item">No major Bloomberg, Seeking Alpha, CNBC, or other high-signal headline was available in the current free feed.</div></div>'
    blocks = []
    for news_item in headlines:
        source = news_item.source or detect_news_source(news_item.title, news_item.link) or "News"
        title = clean_headline(news_item.title)
        impact = headline_impact_summary(item, news_item)
        title_html = html.escape(title)
        if news_item.link:
            title_html = f'<a href="{html.escape(news_item.link)}">{title_html}</a>'
        blocks.append(
            f"""<div class="headline-item">
  <div class="headline-source">{html.escape(source)}</div>
  <div class="headline-title">{title_html}</div>
  <div class="headline-impact">{html.escape(impact)}</div>
</div>"""
        )
    return f"""<div class="headline-list">
{''.join(blocks)}
</div>"""


def select_major_headlines(item: Analysis, limit: int) -> list[NewsItem]:
    clean_items = dedupe_news(non_low_value_news(item.news))
    if not clean_items:
        return []

    selected: list[NewsItem] = []
    for source in PREFERRED_NEWS_SOURCES:
        matches = [news_item for news_item in clean_items if (news_item.source or detect_news_source(news_item.title, news_item.link)) == source]
        if matches:
            selected.append(best_headline(matches, item))
        if len(selected) >= limit:
            return selected[:limit]

    remaining = [news_item for news_item in clean_items if news_item not in selected]
    fallback = major_news_items(remaining) or remaining
    for news_item in sorted(fallback, key=lambda candidate: headline_signal_score(candidate, item), reverse=True):
        selected.append(news_item)
        if len(selected) >= limit:
            break
    return selected[:limit]


def best_headline(news: list[NewsItem], item: Analysis) -> NewsItem:
    return max(news, key=lambda candidate: headline_signal_score(candidate, item))


def dedupe_news(news: list[NewsItem]) -> list[NewsItem]:
    unique: list[NewsItem] = []
    seen: set[str] = set()
    for news_item in news:
        key = clean_headline(news_item.title).lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(news_item)
    return unique


def headline_signal_score(news_item: NewsItem, item: Analysis) -> int:
    title = news_item.title.lower()
    source = news_item.source or detect_news_source(news_item.title, news_item.link)
    score = 0
    if source in PREFERRED_NEWS_SOURCES:
        score += 20
    if any(contains_keyword(title, term) for term in relevance_terms(item.symbol, item.name)):
        score += 10
    if any(contains_keyword(title, keyword) for keyword in MAJOR_NEWS_KEYWORDS):
        score += 8
    if any(contains_keyword(title, keyword) for keyword in DEAL_CONTRACT_KEYWORDS + EARNINGS_GUIDANCE_KEYWORDS + REGULATORY_LEGAL_KEYWORDS):
        score += 4
    return score


def headline_impact_summary(item: Analysis, news_item: NewsItem) -> str:
    title = clean_headline(news_item.title)
    text = title.lower()
    direction = item.setup_direction or "TRADE"
    sector = SYMBOL_SECTORS.get(item.symbol.upper(), "")

    if any(contains_keyword(text, keyword) for keyword in EARNINGS_GUIDANCE_KEYWORDS):
        impact = "This is an earnings-expectations item, so it can move the stock if traders think revenue, margins, or guidance are being reset."
    elif any(contains_keyword(text, keyword) for keyword in DEAL_CONTRACT_KEYWORDS):
        impact = "This points to deal or contract activity, which can improve sentiment if it adds visible demand, revenue, or strategic value."
    elif any(contains_keyword(text, keyword) for keyword in REGULATORY_LEGAL_KEYWORDS):
        impact = "This creates legal or regulatory overhang, which can pressure valuation and make upside harder until the risk clears."
    elif any(contains_keyword(text, keyword) for keyword in PRODUCT_TECH_KEYWORDS):
        impact = "This is a product or technology catalyst, so the market will care if it changes growth expectations or competitive positioning."
    elif any(contains_keyword(text, keyword) for keyword in GEOPOLITICAL_KEYWORDS):
        if sector == "energy":
            impact = "This is directly tied to oil/geopolitical risk, which can shift crude expectations and make energy names more reactive."
        else:
            impact = "This is macro/geopolitical risk, which can affect the stock through risk appetite, supply chains, rates, or sector rotation."
    elif "upgrade" in text or "downgrade" in text or "price target" in text:
        impact = "This is mostly a sentiment/analyst-expectations item; useful for context, but price confirmation matters more."
    else:
        impact = "This is a stock-specific context item; it matters most if price confirms that traders are reacting to it."

    if direction == "CALL":
        return f"{impact} For this CALL setup, it is supportive only if buyers defend the dip and reclaim the listed trigger."
    if direction == "PUT":
        return f"{impact} For this PUT setup, it matters if the headline helps sellers reject the spike or break the listed trigger."
    return impact


def chart_card(rank: int, item: Analysis) -> str:
    four_hour_dates = item.four_hour_dates or item.chart_dates or []
    four_hour_opens = item.four_hour_opens or item.chart_opens or []
    four_hour_highs = item.four_hour_highs or item.chart_highs or []
    four_hour_lows = item.four_hour_lows or item.chart_lows or []
    four_hour_closes = item.four_hour_closes or item.chart_closes or []
    four_hour_chart = render_chart_section(
        rank,
        item.symbol,
        item.setup_direction,
        "4-hour candle chart",
        "Recent 4-hour candles",
        four_hour_dates,
        four_hour_opens,
        four_hour_highs,
        four_hour_lows,
        four_hour_closes,
        item,
        show_pattern=True,
    )
    intraday_chart = render_chart_section(
        rank,
        item.symbol,
        item.setup_direction,
        "15-minute candle chart",
        "Recent 15-minute candles",
        item.intraday_dates or [],
        item.intraday_opens or [],
        item.intraday_highs or [],
        item.intraday_lows or [],
        item.intraday_closes or [],
        item,
        show_pattern=False,
    )
    return f"""<article class="chart-card">
  <div>
    {four_hour_chart}
    {intraday_chart}
  </div>
</article>"""


def render_chart_section(
    rank: int,
    symbol: str,
    direction: str,
    title: str,
    meta_label: str,
    dates: list[str],
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    item: Analysis,
    show_pattern: bool = True,
) -> str:
    chart = render_plotly_candle_chart(rank, symbol, title, dates, opens, highs, lows, closes, direction, item, show_pattern)
    timeframe = "15m" if "15" in title else "4H" if "4-hour" in title else "1D"
    return f"""<section class="chart-section">
  <div class="chart-title">{html.escape(timeframe)}</div>
  {chart}
</section>"""


def expanded_news_summary(item: Analysis) -> str:
    company_news = relevant_company_news(item.news, item)
    macro_news = relevant_macro_news(item.macro_news or [], item.symbol)
    research_news = select_research_news(item, company_news, macro_news, limit=10)
    if not company_news and not macro_news:
        if research_news:
            return f"Catalyst summary / research brief: {deep_catalyst_research_brief(item, research_news, [], weak_catalyst=True)}"
        return (
            "Catalyst summary / research brief: The available feeds did not show a meaningful company-specific or sector-relevant catalyst after filtering out low-value headlines. "
            "That means this setup is being driven mostly by price action unless fresh news appears."
        )

    company_major = company_news
    major_news = company_major + macro_news
    if not major_news:
        if research_news:
            return f"Catalyst summary / research brief: {deep_catalyst_research_brief(item, research_news, [], weak_catalyst=True)}"
        return (
            f"Catalyst summary / research brief: The available feed for {item.symbol} did not show a clean major catalyst after filtering out analyst/listicle noise and unrelated macro headlines. "
            "That makes the news backdrop low-conviction rather than a clear reason for the stock to move."
        )

    return f"Catalyst summary / research brief: {deep_catalyst_research_brief(item, research_news or major_news, macro_news)}"


def select_research_news(item: Analysis, company_news: list[NewsItem], macro_news: list[NewsItem], limit: int = 10) -> list[NewsItem]:
    terms = relevance_terms(item.symbol, item.name)
    directly_relevant = [
        news_item
        for news_item in non_low_value_news(item.news)
        if any(contains_keyword(news_item.title.lower(), term) for term in terms)
    ]
    combined = dedupe_news(company_news + select_major_headlines(item, limit) + directly_relevant + macro_news)
    if not combined:
        return []
    return sorted(combined, key=lambda news_item: headline_signal_score(news_item, item), reverse=True)[:limit]


def deep_catalyst_research_brief(
    item: Analysis,
    research_news: list[NewsItem],
    macro_news: list[NewsItem],
    weak_catalyst: bool = False,
) -> str:
    symbol = item.symbol
    direction = item.setup_direction or "TRADE"
    titles = [clean_headline(news_item.title) for news_item in research_news if news_item.title.strip()]
    topics = event_topics(titles)
    source_names = sorted({(news_item.source or detect_news_source(news_item.title, news_item.link) or "News") for news_item in research_news})
    source_text = ", ".join(source_names[:6]) if source_names else "available feeds"
    topic_text = ", ".join(topics[:5]) if topics else "company-specific news flow"

    setup = catalyst_story_summary(item, research_news, topics, source_text, weak_catalyst)

    why = detailed_catalyst_why_it_matters(item, topics, research_news)
    macro = detailed_macro_connection(item, macro_news, topics)
    shock_warning = oil_shock_trade_warning(item)
    trade = f"Trade read: keep this as a {direction} setup only if the tape confirms the headline with volume and level control."
    if direction == "CALL":
        confirmation = (
            "CALL confirmation: dip absorption, a higher low, or a reclaim with volume. No confirmation, no trade."
        )
    elif direction == "PUT":
        confirmation = (
            "PUT confirmation: failed follow-through, a lower high, or rejection of the spike. No rejection, no trade."
        )
    else:
        confirmation = "The catalyst is actionable only with price and volume confirmation."
    risk = catalyst_invalidation_read(item, topics)
    return " ".join(part for part in (setup, f"Main themes: {topic_text}.", why, macro, shock_warning, trade, confirmation, risk) if part)


def research_event_line(news_item: NewsItem) -> str:
    source = news_item.source or detect_news_source(news_item.title, news_item.link) or "News"
    return f"{source}: {headline_event_phrase(news_item.title)}"


def catalyst_story_summary(
    item: Analysis,
    research_news: list[NewsItem],
    topics: list[str],
    source_text: str,
    weak_catalyst: bool,
) -> str:
    symbol = item.symbol
    titles = [headline_event_phrase(news_item.title) for news_item in research_news if news_item.title.strip()]
    lead = titles[0] if titles else "the available company-specific coverage"
    sector = SYMBOL_SECTORS.get(symbol.upper(), "")
    if weak_catalyst:
        opener = f"After reviewing {source_text}, I found useful context for {symbol}, but not a clean single catalyst."
    else:
        opener = f"After reviewing {source_text}, the story around {symbol} is mainly about {lead}."

    details: list[str] = []
    if "earnings, guidance, or margin pressure" in topics:
        details.append("Estimate, margin, and guidance sensitivity are in play.")
    if "AI strategy, spending, or demand" in topics or "cloud or data-center demand" in topics:
        details.append("The AI/cloud angle comes down to monetization versus capex drag.")
    if "deal, contract, or licensing activity" in topics:
        details.append("The deal/customer-demand angle gives traders a concrete repricing hook around future revenue.")
    if "regulatory or public scrutiny" in topics or "active lawsuit or legal challenge" in topics or "regulatory approval or withdrawal risk" in topics:
        details.append("Regulatory/legal overhang keeps buyer conviction conditional.")
    if "Middle East or geopolitical risk" in topics or "trade-policy or supply-chain pressure" in topics:
        details.append("Macro/geopolitical stress is active in the tape and can override single-name strength.")
    if "rates and inflation expectations" in topics:
        details.append("Rates and inflation are pressuring multiples, credit sensitivity, and risk appetite.")
    if "oil-price sensitivity" in topics:
        details.append("Oil/supply risk is moving energy cash-flow expectations and transport-sensitive margins.")
    if sector == "financials" and "IPO-related sentiment" in topics:
        details.append("For financials, IPO/dealmaking flow feeds directly into fee and trading-revenue expectations.")
    if not details:
        details.append("No single dominant catalyst; this is a positioning/sentiment read until price confirms.")
    return " ".join([opener] + details)


def shorten_event_phrase(text: str, limit: int = 95) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" .")
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def human_join(items: list[str]) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def detailed_catalyst_why_it_matters(item: Analysis, topics: list[str], news: list[NewsItem]) -> str:
    symbol = item.symbol
    sector = SYMBOL_SECTORS.get(symbol.upper(), "")
    points: list[str] = []
    if "earnings, guidance, or margin pressure" in topics:
        points.append("fresh earnings/guidance pressure on the forward estimate path")
    if "AI strategy, spending, or demand" in topics or "cloud or data-center demand" in topics:
        points.append("AI/cloud monetization versus capex risk")
    if "chip-sector momentum" in topics:
        points.append("chip-sector beta and AI-basket spillover")
    if "deal, contract, or licensing activity" in topics:
        points.append("deal/contract visibility around demand, backlog, or strategic validation")
    if "regulatory or public scrutiny" in topics or "active lawsuit or legal challenge" in topics or "regulatory approval or withdrawal risk" in topics:
        points.append("regulatory/legal overhang on the multiple")
    if "Middle East or geopolitical risk" in topics or "trade-policy or supply-chain pressure" in topics:
        points.append("geopolitical/trade-policy stress across risk appetite, supply chains, and input costs")
    if "rates and inflation expectations" in topics:
        points.append("rates/inflation pressure on multiples, demand, and credit beta")
    if "oil-price sensitivity" in topics:
        points.append("oil inventory, crude-price, and supply-risk sensitivity")
    if "IPO-related sentiment" in topics:
        points.append("IPO/dealmaking sensitivity in fee income and risk appetite")
    if not points:
        points.append("positioning and volume sensitivity if traders treat the headline as fresh")

    sector_detail = ""
    if sector == "financials":
        sector_detail = f" For {symbol}, the key read is whether this changes underwriting, advisory revenue, fee income, credit sensitivity, trading activity, or capital-markets appetite."
    elif sector in {"semis", "software"}:
        sector_detail = f" For {symbol}, the key read is whether investors see the story as durable growth or as a spending/valuation risk."
    elif sector == "energy":
        sector_detail = f" For {symbol}, the key read is whether the news changes crude, service demand, production, or cash-flow expectations."
    elif sector == "consumer":
        sector_detail = f" For {symbol}, the key read is whether it changes consumer demand, pricing power, margin pressure, or discretionary spending."
    elif sector == "industrial":
        sector_detail = f" For {symbol}, the key read is whether it changes orders, backlog, defense/aerospace demand, input costs, or delivery timelines."
    elif sector == "healthcare":
        sector_detail = f" For {symbol}, the key read is whether it changes approval odds, reimbursement, drug demand, procedure volume, or expected sales."
    return f"My read: {', and '.join(points)}.{sector_detail}"


def detailed_macro_connection(item: Analysis, macro_news: list[NewsItem], topics: list[str]) -> str:
    relevant_macro = sorted(
        relevant_macro_news(macro_news, item.symbol),
        key=lambda news_item: headline_signal_score(news_item, item),
        reverse=True,
    )[:4] if macro_news else []
    if not relevant_macro:
        return ""
    macro_titles = [clean_headline(news_item.title) for news_item in relevant_macro if news_item.title.strip()]
    macro_topics = event_topics(macro_titles)
    parts: list[str] = []
    if "Middle East or geopolitical risk" in macro_topics or "oil-price sensitivity" in macro_topics:
        parts.append("geopolitical and oil-risk headlines are affecting the broader tape")
    if "rates and inflation expectations" in macro_topics:
        parts.append("rates and inflation expectations remain part of the market backdrop")
    if "trade-policy or supply-chain pressure" in macro_topics:
        parts.append("trade-policy and supply-chain risk can still pressure sentiment")
    if "AI strategy, spending, or demand" in macro_topics or "cloud or data-center demand" in macro_topics:
        parts.append("AI and data-center spending remain major drivers of risk appetite")
    if not parts:
        parts.append("the broader market news is relevant but not clearly one-directional")
    concrete = ""
    if macro_titles:
        concrete = f" Most relevant current item: {shorten_event_phrase(macro_titles[0], 120)}."
    return f"Macro/geopolitical overlay: {human_join(parts)}.{concrete}"


def oil_shock_trade_warning(item: Analysis) -> str:
    shock = macro_oil_shock(item.macro_news or [])
    if not shock.get("active"):
        return ""
    direction = item.setup_direction or "CALL"
    sector = SYMBOL_SECTORS.get(item.symbol.upper(), "")
    evidence = str(shock.get("evidence") or "Strait/Hormuz oil disruption")
    if direction == "CALL" and sector != "energy":
        return (
            f"Macro override: {evidence}. That is a risk-off oil shock, so I would be skeptical of normal CALL setups today unless the stock shows clear relative strength against the tape. "
            "Broad tech, consumer, healthcare, and financial calls need a much higher confirmation bar while oil inflation, shipping risk, and geopolitical escalation are pressuring multiples."
        )
    if direction == "CALL" and sector == "energy":
        return (
            f"Macro override: {evidence}. Energy CALLs have direct crude-supply backing here, but I still would not chase an extended open."
        )
    if direction == "PUT" and sector != "energy":
        return (
            f"Macro override: {evidence}. Defensive PUT bias is cleaner in non-energy names while traders de-risk around oil inflation, shipping disruption, and geopolitical uncertainty."
        )
    if direction == "PUT" and sector == "energy":
        return (
            f"Macro override: {evidence}. That works against an energy PUT unless crude fades or the stock rejects despite the oil-risk tailwind."
        )
    return ""


def catalyst_invalidation_read(item: Analysis, topics: list[str]) -> str:
    direction = item.setup_direction or "TRADE"
    if direction == "CALL":
        return "What would weaken the trade: the headlines fail to produce buying volume, the stock loses the listed dip zone, or new macro/news flow turns risk-off."
    if direction == "PUT":
        return "What would weaken the trade: sellers fail to reject the move, the stock holds above resistance, or fresh positive news overwhelms the bearish setup."
    return "What would weaken the trade: no volume response, no price confirmation, or a new headline that contradicts the original catalyst."


def expanded_catalyst_digest(item: Analysis, company_news: list[NewsItem], macro_news: list[NewsItem]) -> str:
    event_news = select_event_news(item, company_news, macro_news)
    titles = [clean_headline(news_item.title) for news_item in event_news if news_item.title.strip()]
    topics = event_topics(titles)
    event_sentence = summarize_specific_events(item, event_news)
    headline_context = headline_context_summary(item, event_news)
    impact_sentence = catalyst_impact_opinion(item, topics, event_news)
    broader_read = broader_catalyst_read(item, topics, event_news)
    direction_sentence = catalyst_direction_opinion(item, topics)
    return " ".join(sentence for sentence in (event_sentence, headline_context, impact_sentence, broader_read, direction_sentence) if sentence)


def classify_news_categories(news: list[NewsItem]) -> dict[str, list[str]]:
    return {
        "geopolitical/macro": keyword_hits(news, GEOPOLITICAL_KEYWORDS),
        "deal/contract": keyword_hits(news, DEAL_CONTRACT_KEYWORDS),
        "earnings/guidance": keyword_hits(news, EARNINGS_GUIDANCE_KEYWORDS),
        "regulatory/legal": keyword_hits(news, REGULATORY_LEGAL_KEYWORDS),
        "product/technology": keyword_hits(news, PRODUCT_TECH_KEYWORDS),
        "hype/social": keyword_hits(news, HYPE_KEYWORDS),
        "bullish": keyword_hits(news, POSITIVE_CATALYST_KEYWORDS),
        "bearish": keyword_hits(news, NEGATIVE_CATALYST_KEYWORDS),
    }


def professional_catalyst_digest(
    item: Analysis,
    company_news: list[NewsItem],
    macro_news: list[NewsItem],
    categories: dict[str, list[str]],
    direction: str,
) -> str:
    sentences: list[str] = []
    sentences.append(current_event_summary(item, company_news, macro_news))
    sentences.append(chart_setup_context(item))
    sentences.append(direction_event_read(categories, direction))
    return " ".join(sentence for sentence in sentences if sentence)


def summarize_specific_events(item: Analysis, news: list[NewsItem]) -> str:
    if not news:
        return f"The filtered feeds did not surface a specific event for {item.symbol}."
    summaries = [plain_event_summary(news_item) for news_item in news[:3]]
    if len(summaries) == 1:
        event_text = summaries[0]
    elif len(summaries) == 2:
        event_text = f"{summaries[0]}; also, {summaries[1]}"
    else:
        event_text = f"{summaries[0]}; also, {summaries[1]}; and {summaries[2]}"
    return f"The main news I found is that {event_text}."


def plain_event_summary(news_item: NewsItem) -> str:
    title = headline_event_phrase(news_item.title)
    source = news_item.source or detect_news_source(news_item.title, news_item.link)
    if source:
        return f"{source} is covering {title}"
    return title if title else "a relevant catalyst is developing"


def headline_context_summary(item: Analysis, news: list[NewsItem]) -> str:
    if not news:
        return ""
    pieces: list[str] = []
    labels = ("first", "second", "third")
    for index, news_item in enumerate(news[:3]):
        pieces.append(f"{labels[index].title()} item: {single_headline_context(item, news_item)}")
    return " ".join(pieces)


def single_headline_context(item: Analysis, news_item: NewsItem) -> str:
    title = clean_headline(news_item.title)
    text = title.lower()
    symbol = item.symbol
    sector = SYMBOL_SECTORS.get(symbol.upper(), "")

    if any(contains_keyword(text, keyword) for keyword in EARNINGS_GUIDANCE_KEYWORDS):
        return (
            f"earnings, revenue, cash flow, or guidance expectations are in focus for {symbol}; traders will care most if the forward numbers are moving, not just the reported quarter."
        )
    if sector == "financials" and any(contains_keyword(text, keyword) for keyword in ("ipo", "dealmaking", "deal", "trading", "underwriting")):
        return (
            f"it speaks to capital-markets activity. For {symbol}, stronger IPOs, advisory work, trading activity, or deal financing can support fee expectations, while risk-off headlines can make clients pause transactions."
        )
    if any(contains_keyword(text, keyword) for keyword in DEAL_CONTRACT_KEYWORDS):
        return (
            f"deal, contract, partnership, or customer-demand signal for {symbol}; useful if it improves future revenue visibility, backlog, or strategic positioning."
        )
    if any(contains_keyword(text, keyword) for keyword in REGULATORY_LEGAL_KEYWORDS):
        return (
            f"legal, regulatory, approval, or investigation risk around {symbol}; likely to keep buyer conviction conditional."
        )
    if any(contains_keyword(text, keyword) for keyword in PRODUCT_TECH_KEYWORDS):
        return (
            f"product, AI, cloud, chip, or technology positioning for {symbol}; the market is weighing measurable revenue against spending and execution risk."
        )
    if any(contains_keyword(text, keyword) for keyword in GEOPOLITICAL_KEYWORDS):
        if sector == "energy":
            return (
                f"it is tied to oil, supply risk, or geopolitical tension. For {symbol}, that can move expectations for crude prices and cash flow much faster than ordinary company news."
            )
        return (
            f"geopolitical, tariff, China, export-control, or supply-chain pressure around {symbol}; demand assumptions, input costs, multiples, and risk appetite are the pressure points."
        )
    if any(contains_keyword(text, keyword) for keyword in HYPE_KEYWORDS):
        return (
            f"attention and positioning headline for {symbol}; useful only if volume and momentum follow."
        )
    return (
        f"it gives context for how traders are talking about {symbol}. I would not treat it as a standalone catalyst unless the stock reacts with stronger volume or a clean break/reclaim of the relevant levels."
    )


def catalyst_impact_opinion(item: Analysis, topics: list[str], news: list[NewsItem]) -> str:
    symbol = item.symbol
    sector = SYMBOL_SECTORS.get(symbol.upper(), "")
    if "earnings, guidance, or margin pressure" in topics:
        return f"My read: {symbol} is trading around the next estimate reset: earnings quality, cash flow, margin commentary, and guidance."
    if sector == "financials" and ("IPO-related sentiment" in topics or "deal, contract, or licensing activity" in topics):
        return f"My read: {symbol} has capital-markets sensitivity here: underwriting, advisory revenue, trading activity, and overall risk appetite."
    if "deal, contract, or licensing activity" in topics:
        return f"My read: the deal/contract angle gives {symbol} a concrete repricing hook: revenue visibility, backlog, customer demand, or strategic value."
    if "regulatory or public scrutiny" in topics or "active lawsuit or legal challenge" in topics or "regulatory approval or withdrawal risk" in topics:
        return f"My read: regulatory/legal overhang is the key risk for {symbol}; buyers need proof the market is willing to look through it."
    if "AI strategy, spending, or demand" in topics or "cloud or data-center demand" in topics:
        return f"My read: {symbol}'s AI/cloud read is monetization versus capex and execution risk."
    if "oil-price sensitivity" in topics or (sector == "energy" and "Middle East or geopolitical risk" in topics):
        return f"My read: {symbol} is tied to oil inventory, crude-price, and geopolitical supply risk; cash-flow expectations can move fast."
    if "Middle East or geopolitical risk" in topics or "trade-policy or supply-chain pressure" in topics:
        return f"My read: {symbol} has geopolitical/trade-policy exposure through risk appetite, supply-chain assumptions, input costs, and demand."
    if "IPO-related sentiment" in topics:
        return f"My read: IPO/dealmaking headlines are feeding risk appetite around {symbol} and related high-momentum names."
    if news:
        return f"My read: {symbol} needs volume and price confirmation before I treat these headlines as more than background noise."
    return f"My read: not enough event detail to call the news a strong catalyst for {symbol}."


def broader_catalyst_read(item: Analysis, topics: list[str], news: list[NewsItem]) -> str:
    symbol = item.symbol
    if not news:
        return ""
    bullish = bool(
        "deal, contract, or licensing activity" in topics
        or "AI strategy, spending, or demand" in topics
        or "cloud or data-center demand" in topics
        or "earnings, guidance, or margin pressure" in topics
        or "oil-price sensitivity" in topics
    )
    risk = bool(
        "regulatory or public scrutiny" in topics
        or "active lawsuit or legal challenge" in topics
        or "regulatory approval or withdrawal risk" in topics
        or "Middle East or geopolitical risk" in topics
        or "trade-policy or supply-chain pressure" in topics
        or "cost control or capital-spending concerns" in topics
    )
    if bullish and risk:
        return (
            f"The catalyst backdrop is mixed rather than one-sided: there is a real reason traders could bid {symbol}, but there is also enough risk in the headlines that I would want confirmation instead of assuming the news is automatically bullish."
        )
    if bullish:
        return (
            f"The catalyst backdrop is constructive because the headlines give traders a reason to believe expectations may improve. That does not guarantee a move, but it gives the stock a better story if buyers start pressing."
        )
    if risk:
        return (
            f"The catalyst backdrop is risk-heavy because the headlines give traders a reason to question valuation, demand, margins, or future revenue. That can matter most when the chart is already extended or struggling to reclaim strength."
        )
    return (
        f"The catalyst backdrop is moderate. I do not see a single overwhelming event in the filtered headlines, but there is enough stock-specific context that I would watch whether traders start treating it as fresh information."
    )


def catalyst_direction_opinion(item: Analysis, topics: list[str]) -> str:
    direction = item.setup_direction or "TRADE"
    bullish = bool(
        "deal, contract, or licensing activity" in topics
        or "AI strategy, spending, or demand" in topics
        or "cloud or data-center demand" in topics
        or "earnings, guidance, or margin pressure" in topics
    )
    risk = bool(
        "regulatory or public scrutiny" in topics
        or "active lawsuit or legal challenge" in topics
        or "Middle East or geopolitical risk" in topics
        or "trade-policy or supply-chain pressure" in topics
    )
    if direction == "CALL":
        if bullish and not risk:
            return "That gives the CALL idea a cleaner catalyst if buyers step in, because the news has a plausible reason to pull dip-buyers back into the name."
        if bullish and risk:
            return "That makes the CALL idea more conditional: there is upside fuel in the headlines, but the market still has to prove it is willing to absorb the risk."
        if risk:
            return "That makes the CALL idea more fragile, because the news could keep buyers cautious unless the stock clearly reclaims strength."
        return "That leaves the CALL idea mostly dependent on technical rebound behavior rather than a strong news driver."
    if direction == "PUT":
        if risk:
            return "That can support the PUT idea if the stock starts rejecting higher prices, because the news gives sellers a reason to question the recent move."
        if bullish:
            return "That makes the PUT idea more contrarian, because the headline backdrop is not obviously bearish; the trade needs clear rejection on the tape."
        return "That leaves the PUT idea mostly dependent on technical exhaustion rather than a strong news driver."
    return "That makes the catalyst useful context, but price confirmation still decides whether it is actionable."


def current_event_summary(item: Analysis, company_news: list[NewsItem], macro_news: list[NewsItem]) -> str:
    symbol = item.symbol
    sector = SYMBOL_SECTORS.get(symbol.upper(), "")
    event_news = select_event_news(item, company_news, macro_news)
    titles = [clean_headline(news_item.title) for news_item in event_news if news_item.title.strip()]
    topics = event_topics(titles)
    specific_events = specific_event_clause(event_news)

    if sector == "energy" and ("Middle East or geopolitical risk" in topics or "oil-price sensitivity" in topics):
        return (
            f"Current event: {specific_events}. "
            f"For {symbol}, that is directly relevant because crude-supply risk can change oil-price expectations, which feeds into cash-flow expectations for energy producers and service names."
        )
    if sector == "financials" and ("IPO-related sentiment" in topics or "deal, contract, or licensing activity" in topics or "rates and inflation expectations" in topics):
        return (
            f"Current event: {specific_events}. "
            f"For {symbol}, the read is capital-markets beta: investment-banking fees, underwriting appetite, advisory work, and client risk-taking."
        )
    if sector in {"semis", "software"} and ("AI strategy, spending, or demand" in topics or "cloud or data-center demand" in topics):
        return (
            f"Current event: {specific_events}. "
            f"For {symbol}, the read is AI monetization versus cost/capex overhang."
        )
    if sector in {"semis", "software"} and "trade-policy or supply-chain pressure" in topics:
        return (
            f"Current event: {specific_events}. "
            f"For {symbol}, the pressure points are China/Taiwan restrictions, advanced-chip demand assumptions, supply chains, and valuation multiples."
        )
    if sector == "consumer" and ("rates and inflation expectations" in topics or "trade-policy or supply-chain pressure" in topics):
        return (
            f"Current event: {specific_events}. "
            f"For {symbol}, the pressure points are household budgets, input costs, demand, margins, and guidance."
        )
    if sector == "industrial" and ("Middle East or geopolitical risk" in topics or "trade-policy or supply-chain pressure" in topics):
        return (
            f"Current event: {specific_events}. "
            f"For {symbol}, the pressure points are orders, backlog quality, input costs, and delivery timelines."
        )
    if sector == "healthcare" and ("regulatory approval or withdrawal risk" in topics or "regulatory or public scrutiny" in topics):
        return (
            f"Current event: {specific_events}. "
            f"For {symbol}, the key variables are approval risk, withdrawal risk, reimbursement, expected drug revenue, and investor confidence."
        )
    if company_news:
        return f"Current event: {specific_events}. {explain_company_topics(symbol, topics)}"
    if macro_news:
        return f"Current event: {specific_events}. {explain_macro_topics(symbol, sector, topics)}"
    return f"Current event: the available feed for {symbol} is thin and does not show a clear catalyst."


def select_event_news(item: Analysis, company_news: list[NewsItem], macro_news: list[NewsItem], limit: int = 3) -> list[NewsItem]:
    combined = dedupe_news(company_news + macro_news + select_major_headlines(item, limit))
    if not combined:
        return []
    return sorted(combined, key=lambda news_item: headline_signal_score(news_item, item), reverse=True)[:limit]


def specific_event_clause(news: list[NewsItem]) -> str:
    if not news:
        return "the available feed does not name a specific event"
    clauses: list[str] = []
    for news_item in news[:3]:
        title = clean_headline(news_item.title)
        source = news_item.source or detect_news_source(news_item.title, news_item.link)
        event = headline_event_phrase(title)
        if source:
            clauses.append(f"{source} is reporting {event}")
        else:
            clauses.append(f"the feed is reporting {event}")
    if len(clauses) == 1:
        return clauses[0]
    if len(clauses) == 2:
        return f"{clauses[0]}; {clauses[1]}"
    return f"{clauses[0]}; {clauses[1]}; and {clauses[2]}"


def headline_event_phrase(title: str) -> str:
    cleaned = clean_headline(title)
    cleaned = re.sub(r"^(why|how)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if len(cleaned) > 145:
        cleaned = cleaned[:142].rstrip() + "..."
    return cleaned if cleaned else "a relevant catalyst"


def chart_setup_context(item: Analysis) -> str:
    direction = item.setup_direction or "TRADE"
    notes = item.setup_notes or item.notes
    notes_text = "; ".join(notes[:3]) if notes else "the current setup"
    if item.setup_strategy == "reversal" and direction == "CALL":
        move = f"after a {format_pct(item.return_20d)} 20-day pullback" if item.return_20d is not None else "after a recent pullback"
        return f"Chart context: {item.symbol} is being watched as a dip-rebound CALL setup {move}; the technical case is {notes_text}."
    if item.setup_strategy == "reversal" and direction == "PUT":
        move = f"after a {format_pct(item.return_20d)} 20-day runup" if item.return_20d is not None else "after a recent runup"
        return f"Chart context: {item.symbol} is being watched as a spike-fade PUT setup {move}; the technical case is {notes_text}."
    return f"Chart context: {item.symbol} is being watched because {notes_text}."


def company_event_summary(symbol: str, news: list[NewsItem]) -> str:
    titles = [clean_headline(item.title) for item in news[:3] if item.title.strip()]
    text = " ".join(title.lower() for title in titles)
    if "earnings" in text or "guidance" in text or "revenue" in text:
        theme = "earnings and estimate expectations"
    elif "contract" in text or "deal" in text or "partnership" in text or "wins" in text:
        theme = "deal or contract activity"
    elif "lawsuit" in text or "probe" in text or "investigation" in text or "scrutiny" in text:
        theme = "legal or regulatory pressure"
    elif "ai" in text or "data center" in text or "cloud" in text or "chip" in text:
        theme = "AI, data-center, cloud, or technology demand"
    elif "launch" in text or "platform" in text or "product" in text:
        theme = "product or platform activity"
    else:
        theme = "company-specific developments"
    explanation = explain_company_topics(symbol, event_topics(titles))
    return f"Company-specific news around {symbol} is centered on {theme}. {explanation}"


def macro_event_summary(symbol: str, news: list[NewsItem]) -> str:
    titles = [clean_headline(item.title) for item in news[:3] if item.title.strip()]
    text = " ".join(title.lower() for title in titles)
    sector = SYMBOL_SECTORS.get(symbol.upper(), "")
    if sector == "energy":
        theme = "energy and geopolitical risk"
    elif sector in {"semis", "software"} and ("tariff" in text or "china" in text or "export control" in text or "taiwan" in text):
        theme = "trade policy and geopolitical supply-chain risk"
    elif sector in {"semis", "software"}:
        theme = "AI, cloud, and technology risk appetite"
    elif sector == "financials":
        theme = "rates, IPO/dealmaking, and risk appetite"
    elif sector == "consumer":
        theme = "consumer spending, inflation, and tariff sensitivity"
    elif sector == "industrial":
        theme = "defense, aerospace, supply-chain, and geopolitical demand"
    elif sector == "healthcare":
        theme = "healthcare policy, drug approvals, and regulatory risk"
    elif "fed" in text or "rates" in text or "inflation" in text or "yield" in text:
        theme = "rates, inflation, and risk appetite"
    else:
        theme = "sector-relevant macro news"
    explanation = explain_macro_topics(symbol, sector, event_topics(titles))
    return f"Relevant macro context for {symbol} is focused on {theme}. {explanation}"


def explain_company_topics(symbol: str, topics: list[str]) -> str:
    explanations: list[str] = []
    if "deal, contract, or licensing activity" in topics:
        explanations.append("The important point is possible new or expanded revenue tied to a deal, contract, partnership, or licensing stream.")
    if "AI strategy, spending, or demand" in topics:
        explanations.append("The market is watching whether AI demand is becoming a real earnings driver or just a spending burden.")
    if "cloud or data-center demand" in topics:
        explanations.append("Data-center/cloud references frame demand strength, capacity spending, and margin pressure.")
    if "active lawsuit or legal challenge" in topics or "regulatory or public scrutiny" in topics:
        explanations.append("The risk is that legal or regulatory pressure can cap upside, create headline overhang, or force investors to discount future growth.")
    if "regulatory approval or withdrawal risk" in topics:
        explanations.append("Approval or withdrawal risk can quickly change expected future sales, especially for healthcare names.")
    if "earnings, guidance, or margin pressure" in topics:
        explanations.append("The key issue is whether expectations for revenue, margins, or guidance are improving or deteriorating.")
    if "possible spin-off or restructuring" in topics:
        explanations.append("A spin-off or restructuring headline can change how investors value the business and may increase short-term volatility.")
    if "new product or platform activity" in topics:
        explanations.append("Product or platform news can help if traders believe it expands the addressable market or strengthens competitive positioning.")
    if "workforce restructuring or labor concerns" in topics:
        explanations.append("Workforce headlines can cut both ways: cost discipline may help margins, but internal disruption can weaken confidence.")
    if "cost control or capital-spending concerns" in topics:
        explanations.append("Spending and capex concerns pressure free cash flow and valuation multiples.")
    if "IPO-related sentiment" in topics:
        explanations.append("IPO-related news is mainly sentiment-driven unless it directly changes the company's ownership, balance sheet, or strategic value.")
    if "fleet expansion or freight demand" in topics:
        explanations.append("Fleet or freight references point to demand trends and utilization, which can matter for transportation-linked companies.")
    if "short-term momentum from recent news flow" in topics:
        explanations.append("Recent momentum headlines show traders are reacting, but they do not replace the need for price confirmation.")
    if not explanations:
        explanations.append(f"The available company-specific news is relevant, but it does not show a single clean catalyst for {symbol}.")
    return " ".join(explanations[:3])


def explain_macro_topics(symbol: str, sector: str, topics: list[str]) -> str:
    explanations: list[str] = []
    if sector == "financials":
        if "rates and inflation expectations" in topics:
            explanations.append("For financials, rates and inflation hit net interest income expectations, credit conditions, and valuation multiples.")
        if "deal, contract, or licensing activity" in topics or "IPO-related sentiment" in topics:
            explanations.append("IPO/deal activity feeds investment-banking fees, underwriting appetite, and advisory revenue.")
        if "Middle East or geopolitical risk" in topics:
            explanations.append("Geopolitical stress can increase market volatility, but it can also reduce client confidence and delay deals.")
    elif sector == "energy":
        if "oil-price sensitivity" in topics or "Middle East or geopolitical risk" in topics:
            explanations.append("For an energy stock, Middle East tension and oil-price moves can directly affect crude prices, cash-flow expectations, and the willingness of traders to buy dips.")
        if "deal, contract, or licensing activity" in topics:
            explanations.append("Energy deal activity can signal demand for assets, services, or production capacity.")
    elif sector in {"semis", "software"}:
        if "AI strategy, spending, or demand" in topics or "cloud or data-center demand" in topics:
            explanations.append("For tech, AI/cloud/data-center headlines shape growth expectations and high-multiple appetite.")
        if "trade-policy or supply-chain pressure" in topics or "Middle East or geopolitical risk" in topics:
            explanations.append("Geopolitical risk can pressure tech names through export restrictions, supply-chain uncertainty, and broader risk-off trading.")
    elif sector == "consumer":
        if "rates and inflation expectations" in topics:
            explanations.append("For a consumer stock, inflation and rates affect household spending power, financing costs, and discretionary demand.")
        if "trade-policy or supply-chain pressure" in topics:
            explanations.append("Tariffs or supply-chain pressure can hit input costs, inventory planning, and margins.")
    elif sector == "industrial":
        if "Middle East or geopolitical risk" in topics or "trade-policy or supply-chain pressure" in topics:
            explanations.append("For an industrial stock, geopolitical risk can affect defense demand, aerospace orders, freight activity, and supply-chain reliability.")
        if "deal, contract, or licensing activity" in topics:
            explanations.append("Contract activity changes backlog visibility and revenue expectations.")
    elif sector == "healthcare":
        if "regulatory approval or withdrawal risk" in topics:
            explanations.append("For a healthcare stock, regulatory decisions can quickly alter expected drug revenue and investor confidence.")
        if "rates and inflation expectations" in topics:
            explanations.append("Rates can still matter through valuation pressure, especially for longer-duration growth assets.")

    if not explanations:
        if "rates and inflation expectations" in topics:
            explanations.append("Rates and inflation shape overall market risk appetite and valuation multiples.")
        if "Middle East or geopolitical risk" in topics:
            explanations.append("Geopolitical risk can drive volatility and risk-off positioning across the market.")
        if "deal, contract, or licensing activity" in topics:
            explanations.append("Deal activity can influence sentiment if it points to stronger demand or capital-market activity.")
    if not explanations:
        explanations.append(f"The macro feed is relevant to {symbol}'s sector, but it does not show a single clear event driver.")
    return " ".join(explanations[:3])


def direction_event_read(categories: dict[str, list[str]], direction: str) -> str:
    bullish = bool(categories["bullish"] or categories["deal/contract"] or categories["product/technology"])
    bearish = bool(categories["bearish"] or categories["regulatory/legal"])
    macro = bool(categories["geopolitical/macro"])
    if direction == "CALL":
        if bullish and not bearish:
            return "Net read: the catalyst backdrop leans supportive for a rebound, but the trade still needs price confirmation."
        if bearish or macro:
            return "Net read: the setup has catalyst risk, so a CALL only makes sense if buyers absorb the news and reclaim the trigger level."
        return "Net read: no strong catalyst edge is visible, so the CALL is mostly a technical rebound setup."
    if direction == "PUT":
        if bearish or macro:
            return "Net read: the catalyst backdrop can support a downside fade if price confirms rejection."
        if bullish:
            return "Net read: the news backdrop is not naturally bearish, so the PUT needs clear technical rejection before acting."
        return "Net read: no strong catalyst edge is visible, so the PUT is mostly a technical fade setup."
    return "Net read: the catalyst backdrop is context only until price confirms direction."


def clean_headline(title: str) -> str:
    cleaned = " ".join(title.replace("—", "-").replace("–", "-").split())
    for separator in (" | ", " - Yahoo Finance", " - Bloomberg", " - CNBC", " - Seeking Alpha", " - Reuters"):
        if separator in cleaned:
            cleaned = cleaned.split(separator, 1)[0]
    return cleaned.rstrip(".")


def event_topics(titles: list[str]) -> list[str]:
    topics: list[str] = []
    text = " ".join(title.lower() for title in titles)
    if contains_keyword(text, "lawsuit"):
        topics.append("active lawsuit or legal challenge")
    if any(contains_keyword(text, keyword) for keyword in ("probe", "investigation", "scrutiny")):
        topics.append("regulatory or public scrutiny")
    if any(contains_keyword(text, keyword) for keyword in ("fda", "approval", "withdrawal")):
        topics.append("regulatory approval or withdrawal risk")
    if any(contains_keyword(text, keyword) for keyword in ("contract", "deal", "licensing", "partnership")):
        topics.append("deal, contract, or licensing activity")
    if any(contains_keyword(text, keyword) for keyword in ("earnings", "guidance", "revenue", "profit", "margin")):
        topics.append("earnings, guidance, or margin pressure")
    if any(contains_keyword(text, keyword) for keyword in ("spin-off", "spinoff")):
        topics.append("possible spin-off or restructuring")
    if any(contains_keyword(text, keyword) for keyword in ("launch", "platform", "product")):
        topics.append("new product or platform activity")
    if any(contains_keyword(text, keyword) for keyword in ("ai", "artificial intelligence")):
        topics.append("AI strategy, spending, or demand")
    if any(contains_keyword(text, keyword) for keyword in ("data center", "cloud")):
        topics.append("cloud or data-center demand")
    if any(contains_keyword(text, keyword) for keyword in ("chip", "semiconductor")):
        topics.append("chip-sector momentum")
    if any(contains_keyword(text, keyword) for keyword in ("workforce", "layoff", "jobs")):
        topics.append("workforce restructuring or labor concerns")
    if any(contains_keyword(text, keyword) for keyword in ("cost", "capex", "spending")):
        topics.append("cost control or capital-spending concerns")
    if contains_keyword(text, "ipo"):
        topics.append("IPO-related sentiment")
    if any(contains_keyword(text, keyword) for keyword in ("fleet", "freight")):
        topics.append("fleet expansion or freight demand")
    if any(contains_keyword(text, keyword) for keyword in ("oil", "crude", "opec")):
        topics.append("oil-price sensitivity")
    if any(contains_keyword(text, keyword) for keyword in ("iran", "middle east", "war", "conflict", "peace")):
        topics.append("Middle East or geopolitical risk")
    if any(contains_keyword(text, keyword) for keyword in ("tariff", "china", "export control", "taiwan")):
        topics.append("trade-policy or supply-chain pressure")
    if any(contains_keyword(text, keyword) for keyword in ("inflation", "fed", "rates", "yield")):
        topics.append("rates and inflation expectations")
    if any(contains_keyword(text, keyword) for keyword in ("surge", "rally", "popped", "recovers")):
        topics.append("short-term momentum from recent news flow")

    if not topics:
        topics = [title for title in titles[:2] if title]

    unique: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        if topic not in seen:
            seen.add(topic)
            unique.append(topic)
    return unique


def join_event_phrases(titles: list[str]) -> str:
    if not titles:
        return "no specific event text was available"
    if len(titles) == 1:
        return titles[0]
    return "; ".join(titles[:3])


def render_plotly_candle_chart(
    rank: int,
    symbol: str,
    title: str,
    dates: list[str],
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    direction: str,
    item: Analysis,
    show_pattern: bool = True,
) -> str:
    index_offset = max(0, len(closes) - 80)
    dates = dates[-80:]
    opens = opens[-80:]
    highs = highs[-80:]
    lows = lows[-80:]
    closes = closes[-80:]
    usable = min(len(dates), len(opens), len(highs), len(lows), len(closes))
    if usable < 2:
        return '<div class="chart-meta">Not enough price history for chart.</div>'
    dates = dates[-usable:]
    opens = opens[-usable:]
    highs = highs[-usable:]
    lows = lows[-usable:]
    closes = closes[-usable:]

    x_values = list(range(usable))
    hover_labels = dates if dates else [str(index + index_offset) for index in x_values]
    chart_id = re.sub(r"[^A-Za-z0-9_-]", "-", f"chart-{rank}-{symbol}-{title}").lower()
    y_low = min(lows)
    y_high = max(highs)
    span = y_high - y_low or max(abs(closes[-1]) * 0.02, 1.0)
    y_padding = span * 0.10

    data: list[dict[str, Any]] = [
        {
            "type": "candlestick",
            "x": x_values,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "text": hover_labels,
            "hovertemplate": "%{text}<br>O %{open:.2f}<br>H %{high:.2f}<br>L %{low:.2f}<br>C %{close:.2f}<extra></extra>",
            "increasing": {"line": {"color": "#22c55e", "width": 1.2}, "fillcolor": "#22c55e"},
            "decreasing": {"line": {"color": "#ef4444", "width": 1.2}, "fillcolor": "#ef4444"},
            "whiskerwidth": 0.55,
        }
    ]
    shapes: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []

    if show_pattern and item.pattern_detection:
        detection = item.pattern_detection

        def local_point(point: tuple[int, float]) -> tuple[int, float] | None:
            local_index = point[0] - index_offset
            if local_index < 0 or local_index >= usable:
                return None
            return local_index, point[1]

        upper_start = local_point(detection.upper_start)
        upper_end = local_point(detection.upper_end)
        lower_start = local_point(detection.lower_start)
        lower_end = local_point(detection.lower_end)
        if upper_start and upper_end and lower_start and lower_end:
            rendered_special = False
            if "inverse head" in detection.pattern_type.lower() and detection.pivot_lows and detection.pivot_highs:
                shoulder_points = [local_point(point) for point in detection.pivot_lows[:3]]
                neckline_points = [local_point(point) for point in detection.pivot_highs[:2]]
                if all(shoulder_points) and all(neckline_points):
                    shoulder_points = [point for point in shoulder_points if point]
                    neckline_points = [point for point in neckline_points if point]
                    data.append(
                        {
                            "type": "scatter",
                            "mode": "lines+markers",
                            "x": [point[0] for point in shoulder_points],
                            "y": [point[1] for point in shoulder_points],
                            "line": {"color": "#22d3ee", "width": 4},
                            "marker": {"color": "#22d3ee", "size": 6},
                            "hovertemplate": "Inverse H&S base<br>y=%{y:.2f}<extra></extra>",
                            "showlegend": False,
                        }
                    )
                    data.append(
                        {
                            "type": "scatter",
                            "mode": "lines",
                            "x": [neckline_points[0][0], upper_end[0]],
                            "y": [neckline_points[0][1], upper_end[1]],
                            "line": {"color": "#facc15", "width": 3, "dash": "dash"},
                            "hovertemplate": "Neckline<br>y=%{y:.2f}<extra></extra>",
                            "showlegend": False,
                        }
                    )
                    shapes.append(
                        {
                            "type": "line",
                            "xref": "x",
                            "yref": "y",
                            "x0": max(0, usable - 8),
                            "x1": usable - 1,
                            "y0": upper_end[1],
                            "y1": upper_end[1],
                            "line": {"color": "#facc15", "width": 2, "dash": "dot"},
                        }
                    )
                    rendered_special = True
            if not rendered_special:
                polygon_x = [upper_start[0], upper_end[0], lower_end[0], lower_start[0], upper_start[0]]
                polygon_y = [upper_start[1], upper_end[1], lower_end[1], lower_start[1], upper_start[1]]
                data.append(
                    {
                        "type": "scatter",
                        "mode": "lines",
                        "x": polygon_x,
                        "y": polygon_y,
                        "fill": "toself",
                        "fillcolor": "rgba(34, 211, 238, 0.14)",
                        "line": {"color": "rgba(34, 211, 238, 0)"},
                        "hoverinfo": "skip",
                        "showlegend": False,
                    }
                )
                data.append(
                    {
                        "type": "scatter",
                        "mode": "lines",
                        "x": [upper_start[0], upper_end[0]],
                        "y": [upper_start[1], upper_end[1]],
                        "line": {"color": "#22d3ee", "width": 4},
                        "hovertemplate": "Upper trendline<br>y=%{y:.2f}<extra></extra>",
                        "showlegend": False,
                    }
                )
                data.append(
                    {
                        "type": "scatter",
                        "mode": "lines",
                        "x": [lower_start[0], lower_end[0]],
                        "y": [lower_start[1], lower_end[1]],
                        "line": {"color": "#22d3ee", "width": 4},
                        "hovertemplate": "Lower trendline<br>y=%{y:.2f}<extra></extra>",
                        "showlegend": False,
                    }
                )
                trigger_point = upper_end if detection.direction == "CALL" else lower_end
                trigger_x0 = min(trigger_point[0], max(0, usable - 8))
                shapes.append(
                    {
                        "type": "line",
                        "xref": "x",
                        "yref": "y",
                        "x0": trigger_x0,
                        "x1": usable - 1,
                        "y0": trigger_point[1],
                        "y1": trigger_point[1],
                        "line": {"color": "#facc15", "width": 2, "dash": "dash"},
                    }
                )

    tick_step = max(1, usable // 5)
    tick_values = list(range(0, usable, tick_step))
    if tick_values[-1] != usable - 1:
        tick_values.append(usable - 1)
    tick_text = [hover_labels[index] for index in tick_values]
    payload = {
        "data": data,
        "layout": {
            "paper_bgcolor": "#111111",
            "plot_bgcolor": "#171717",
            "height": 430,
            "margin": {"l": 46, "r": 76, "t": 12, "b": 34},
            "showlegend": False,
            "dragmode": "pan",
            "xaxis": {
                "type": "linear",
                "showgrid": True,
                "gridcolor": "#262626",
                "zeroline": False,
                "rangeslider": {"visible": False},
                "tickmode": "array",
                "tickvals": tick_values,
                "ticktext": tick_text,
                "tickfont": {"color": "#9b9b9b", "size": 10},
                "linecolor": "#2a2a2a",
            },
            "yaxis": {
                "side": "right",
                "showgrid": True,
                "gridcolor": "#262626",
                "zeroline": False,
                "tickfont": {"color": "#9b9b9b", "size": 10},
                "linecolor": "#2a2a2a",
                "range": [y_low - y_padding, y_high + y_padding],
                "fixedrange": False,
            },
            "shapes": shapes,
            "annotations": annotations,
            "font": {"family": "Inter, ui-sans-serif, system-ui", "color": "#eeeeee"},
            "hoverlabel": {"bgcolor": "#050505", "bordercolor": "#333333", "font": {"color": "#eeeeee"}},
        },
        "config": {
            "displayModeBar": False,
            "responsive": True,
            "scrollZoom": True,
        },
    }
    payload_json = json.dumps(payload, separators=(",", ":"))
    escaped_payload = html.escape(payload_json, quote=True)
    return f"""<div id="{html.escape(chart_id)}" class="plotly-chart" data-plotly-payload="{escaped_payload}"></div>
<script>
(function() {{
  const el = document.getElementById({json.dumps(chart_id)});
  const payload = JSON.parse(el.dataset.plotlyPayload);
  if (window.Plotly) {{
    Plotly.newPlot(el, payload.data, payload.layout, payload.config);
  }} else {{
    el.innerHTML = '<div class="chart-meta">Interactive chart library did not load. Check your internet connection and refresh.</div>';
  }}
}})();
</script>"""


def render_candle_chart(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    direction: str,
    item: Analysis,
    show_pattern: bool = True,
) -> str:
    index_offset = max(0, len(closes) - 60)
    opens = opens[-60:]
    highs = highs[-60:]
    lows = lows[-60:]
    closes = closes[-60:]
    if min(len(opens), len(highs), len(lows), len(closes)) < 2:
        return '<div class="chart-meta">Not enough price history for chart.</div>'
    width = 760
    height = 420
    pad = 26
    label_gutter = 210
    plot_right = width - label_gutter
    plot_width = plot_right - pad
    low = min(lows)
    high = max(highs)
    span = high - low or 1
    count = len(closes)
    step = plot_width / count
    candle_width = max(3, min(8, step * 0.58))

    def y(value: float) -> float:
        return height - pad - ((value - low) / span) * (height - pad * 2)

    grid_lines: list[str] = []
    for grid_index in range(1, 5):
        level = low + span * grid_index / 5
        grid_y = y(level)
        grid_lines.append(
            f'<line x1="{pad}" y1="{grid_y:.1f}" x2="{plot_right}" y2="{grid_y:.1f}" stroke="#262626" stroke-width="1" />'
            f'<text x="{plot_right + 8}" y="{grid_y + 4:.1f}" fill="#737373" font-size="10">${level:.2f}</text>'
        )

    candles: list[str] = []
    for index, (open_price, high_price, low_price, close_price) in enumerate(zip(opens, highs, lows, closes)):
        x = pad + index * step + step / 2
        wick_top = y(high_price)
        wick_bottom = y(low_price)
        body_top = y(max(open_price, close_price))
        body_bottom = y(min(open_price, close_price))
        body_height = max(2, body_bottom - body_top)
        color = "#22c55e" if close_price >= open_price else "#ef4444"
        candles.append(
            f'<line x1="{x:.1f}" y1="{wick_top:.1f}" x2="{x:.1f}" y2="{wick_bottom:.1f}" stroke="{color}" stroke-width="1.4" />'
            f'<rect x="{x - candle_width / 2:.1f}" y="{body_top:.1f}" width="{candle_width:.1f}" height="{body_height:.1f}" fill="{color}" rx="1" />'
        )

    def x(index: int) -> float:
        return pad + index * step + step / 2

    if show_pattern:
        pattern_svg, pattern_label = pattern_overlay_svg(highs, lows, closes, item, x, y, plot_right, height, index_offset)
    else:
        pattern_svg, pattern_label = "", ""

    return f"""<svg class="chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="60 trading day price chart">
  <rect x="{pad}" y="{pad}" width="{plot_width}" height="{height - pad * 2}" fill="#171717" stroke="#2a2a2a" stroke-width="1" />
  {''.join(grid_lines)}
  {''.join(candles)}
  {pattern_svg}
  {pattern_label}
  <text x="{pad}" y="14" fill="#9b9b9b" font-size="11">${high:.2f}</text>
  <text x="{pad}" y="{height - 4}" fill="#9b9b9b" font-size="11">${low:.2f}</text>
</svg>"""


def pattern_overlay_svg(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    item: Analysis,
    x: Any,
    y: Any,
    plot_right: float,
    height: int,
    index_offset: int = 0,
) -> tuple[str, str]:
    notes = " ".join(item.setup_notes or []).lower()
    if len(closes) < 8:
        return "", ""
    start = max(0, len(closes) - 22)
    end = len(closes) - 1
    color = "#22d3ee"
    fill = "#0e7490"
    label = infer_pattern(item)[0]

    def chart_y(value: float) -> float:
        return clamp(y(value), 18, height - 26)

    def clamp_chart_pixel(value: float) -> float:
        return clamp(value, 18, height - 26)

    def label_svg(y_value: float) -> str:
        _label_y = y_value
        badge_x = 36
        badge_y = 36
        text = html.escape(label)
        badge_width = max(92, min(185, len(label) * 7 + 22))
        return (
            f'<rect x="{badge_x}" y="{badge_y - 18}" width="{badge_width}" height="24" rx="7" '
            f'fill="#050505" stroke="{color}" stroke-width="1.2" opacity="0.92" />'
            f'<text x="{badge_x + 10}" y="{badge_y - 2}" fill="{color}" font-size="11" font-weight="800">{text}</text>'
        )

    if item.pattern_detection:
        detection = item.pattern_detection

        def local_point(point: tuple[int, float]) -> tuple[int, float] | None:
            local_index = point[0] - index_offset
            if local_index < 0 or local_index >= len(closes):
                return None
            return local_index, point[1]

        upper_start = local_point(detection.upper_start)
        upper_end = local_point(detection.upper_end)
        lower_start = local_point(detection.lower_start)
        lower_end = local_point(detection.lower_end)
        if not all((upper_start, upper_end, lower_start, lower_end)):
            return "", ""
        upper_start = upper_start or (0, closes[0])
        upper_end = upper_end or (len(closes) - 1, closes[-1])
        lower_start = lower_start or (0, closes[0])
        lower_end = lower_end or (len(closes) - 1, closes[-1])
        projection_index = len(closes) - 1

        def extend_to_current(start_point: tuple[int, float], end_point: tuple[int, float]) -> tuple[int, float]:
            if detection.mode == "validated":
                return end_point
            if end_point[0] >= projection_index or end_point[0] == start_point[0]:
                return end_point
            slope = (end_point[1] - start_point[1]) / (end_point[0] - start_point[0])
            return projection_index, end_point[1] + slope * (projection_index - end_point[0])

        upper_projected = extend_to_current(upper_start, upper_end)
        lower_projected = extend_to_current(lower_start, lower_end)
        upper_start_y = chart_y(upper_start[1])
        upper_projected_y = chart_y(upper_projected[1])
        lower_start_y = chart_y(lower_start[1])
        lower_projected_y = chart_y(lower_projected[1])
        top_y = min(upper_start_y, upper_projected_y, lower_start_y, lower_projected_y)
        breakout_svg = ""
        if detection.breakout_index is not None:
            breakout_local = detection.breakout_index - index_offset
            if 0 <= breakout_local < len(closes):
                arrow_color = "#22c55e" if detection.direction == "CALL" else "#ef4444"
                candle_y = chart_y(closes[breakout_local])
                arrow_tip = clamp_chart_pixel(candle_y - 18 if detection.direction == "CALL" else candle_y + 18)
                arrow_tail = clamp_chart_pixel(candle_y + 16 if detection.direction == "CALL" else candle_y - 16)
                breakout_svg = (
                    f'<line x1="{x(breakout_local):.1f}" y1="{arrow_tail:.1f}" '
                    f'x2="{x(breakout_local):.1f}" y2="{arrow_tip:.1f}" '
                    f'stroke="{arrow_color}" stroke-width="2.8" stroke-linecap="round" />'
                    f'<polygon points="{x(breakout_local) - 5:.1f},{arrow_tip + (7 if detection.direction == "CALL" else -7):.1f} '
                    f'{x(breakout_local):.1f},{arrow_tip:.1f} '
                    f'{x(breakout_local) + 5:.1f},{arrow_tip + (7 if detection.direction == "CALL" else -7):.1f}" '
                    f'fill="{arrow_color}" />'
                )
        trigger_value = upper_projected[1] if detection.direction == "CALL" else lower_projected[1]
        trigger_label = "Breakout" if detection.direction == "CALL" else "Breakdown"
        trigger_y = max(30, min(height - 10, chart_y(trigger_value)))
        trigger_text = f"{trigger_label} ${trigger_value:.2f}"
        trigger_text_width = max(96, min(150, len(trigger_text) * 6 + 18))
        trigger_x = max(36, plot_right - trigger_text_width - 8)
        trigger_svg = (
            f'<line x1="{x(projection_index):.1f}" y1="{trigger_y:.1f}" x2="{plot_right:.1f}" y2="{trigger_y:.1f}" '
            f'stroke="#facc15" stroke-width="1.8" stroke-dasharray="5 4" />'
            f'<rect x="{trigger_x:.1f}" y="{trigger_y - 22:.1f}" width="{trigger_text_width:.1f}" height="20" rx="6" '
            f'fill="#050505" stroke="#facc15" stroke-width="1" opacity="0.9" />'
            f'<text x="{trigger_x + 8:.1f}" y="{trigger_y - 8:.1f}" fill="#facc15" font-size="10" font-weight="800">'
            f'{html.escape(trigger_text)}</text>'
        )
        fill_svg = ""
        if detection.mode in {"strict", "validated"}:
            fill_svg = f'<polygon points="{x(upper_start[0]):.1f},{upper_start_y:.1f} {x(upper_projected[0]):.1f},{upper_projected_y:.1f} {x(lower_projected[0]):.1f},{lower_projected_y:.1f} {x(lower_start[0]):.1f},{lower_start_y:.1f}" fill="{fill}" opacity="0.18" />'
        svg = f"""{fill_svg}
  <line x1="{x(upper_start[0]):.1f}" y1="{upper_start_y:.1f}" x2="{x(upper_projected[0]):.1f}" y2="{upper_projected_y:.1f}" stroke="{color}" stroke-width="3.2" stroke-linecap="round" />
  <line x1="{x(lower_start[0]):.1f}" y1="{lower_start_y:.1f}" x2="{x(lower_projected[0]):.1f}" y2="{lower_projected_y:.1f}" stroke="{color}" stroke-width="3.2" stroke-linecap="round" />
  {trigger_svg}
  {breakout_svg}"""
        return svg, label_svg(top_y - 8)

    def pivots(values: list[float], mode: str, radius: int = 2) -> list[tuple[int, float]]:
        points: list[tuple[int, float]] = []
        for index in range(max(radius, start), len(values) - radius):
            window = values[index - radius : index + radius + 1]
            value = values[index]
            if mode == "high" and value == max(window):
                points.append((index, value))
            if mode == "low" and value == min(window):
                points.append((index, value))
        return points

    def boundary(points: list[tuple[int, float]], fallback_values: list[float]) -> tuple[float, float, float, float]:
        if len(points) >= 2:
            first = points[-3] if len(points) >= 3 else points[0]
            last = points[-1]
            return x(first[0]), y(first[1]), x(last[0]), y(last[1])
        return x(start), y(fallback_values[start]), x(end), y(fallback_values[end])

    if "inverse head-and-shoulders" in notes and len(closes) >= 30:
        points = [
            (len(closes) - 30 + min(range(10), key=lambda idx: lows[-30 + idx]), min(lows[-30:-20])),
            (len(closes) - 20 + min(range(10), key=lambda idx: lows[-20 + idx]), min(lows[-20:-10])),
            (len(closes) - 10 + min(range(10), key=lambda idx: lows[-10 + idx]), min(lows[-10:])),
        ]
        neckline_left_index = len(closes) - 24 + max(range(10), key=lambda idx: highs[-24 + idx])
        neckline_right_index = len(closes) - 12 + max(range(12), key=lambda idx: highs[-12 + idx])
        neckline_left = highs[neckline_left_index]
        neckline_right = highs[neckline_right_index]
        shoulder_path = " ".join(f"{x(index):.1f},{y(value):.1f}" for index, value in points)
        neck_y = (y(neckline_left) + y(neckline_right)) / 2
        svg = f"""<polyline points="{shoulder_path}" fill="none" stroke="{color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
  <line x1="{x(neckline_left_index):.1f}" y1="{y(neckline_left):.1f}" x2="{x(neckline_right_index):.1f}" y2="{y(neckline_right):.1f}" stroke="{color}" stroke-width="2" stroke-dasharray="7 5" />
  <circle cx="{x(points[1][0]):.1f}" cy="{y(points[1][1]):.1f}" r="4" fill="{color}" />"""
        return svg, label_svg(neck_y)

    if "ascending triangle" in notes:
        high_points = pivots(highs, "high")
        low_points = pivots(lows, "low")
        resistance_points = high_points[-3:] if len(high_points) >= 2 else []
        resistance = statistics.fmean(point[1] for point in resistance_points) if resistance_points else max(highs[start : end + 1])
        low_x1, low_y1, low_x2, low_y2 = boundary(low_points, lows)
        resistance_y = y(resistance)
        svg = f"""<polygon points="{x(start):.1f},{resistance_y:.1f} {x(end):.1f},{resistance_y:.1f} {low_x2:.1f},{low_y2:.1f} {low_x1:.1f},{low_y1:.1f}" fill="{fill}" opacity="0.16" />
  <line x1="{x(start):.1f}" y1="{resistance_y:.1f}" x2="{x(end):.1f}" y2="{resistance_y:.1f}" stroke="{color}" stroke-width="2.2" />
  <line x1="{low_x1:.1f}" y1="{low_y1:.1f}" x2="{low_x2:.1f}" y2="{low_y2:.1f}" stroke="{color}" stroke-width="2.2" />"""
        return svg, label_svg(resistance_y - 8)

    if "descending triangle" in notes:
        high_points = pivots(highs, "high")
        support = statistics.median(closes[-4:]) if len(closes) >= 4 else min(lows[start : end + 1])
        high_x1, high_y1, high_x2, high_y2 = boundary(high_points, highs)
        support_y = y(support)
        svg = f"""<polygon points="{x(start):.1f},{support_y:.1f} {x(end):.1f},{support_y:.1f} {high_x2:.1f},{high_y2:.1f} {high_x1:.1f},{high_y1:.1f}" fill="{fill}" opacity="0.16" />
  <line x1="{x(start):.1f}" y1="{support_y:.1f}" x2="{x(end):.1f}" y2="{support_y:.1f}" stroke="{color}" stroke-width="2.2" />
  <line x1="{high_x1:.1f}" y1="{high_y1:.1f}" x2="{high_x2:.1f}" y2="{high_y2:.1f}" stroke="{color}" stroke-width="2.2" />"""
        return svg, label_svg(support_y - 8)

    if "pennant" in notes or "wedge" in notes:
        high_x1, high_y1, high_x2, high_y2 = boundary(pivots(highs, "high"), highs)
        low_x1, low_y1, low_x2, low_y2 = boundary(pivots(lows, "low"), lows)
        svg = f"""<polygon points="{high_x1:.1f},{high_y1:.1f} {high_x2:.1f},{high_y2:.1f} {low_x2:.1f},{low_y2:.1f} {low_x1:.1f},{low_y1:.1f}" fill="{fill}" opacity="0.16" />
  <line x1="{high_x1:.1f}" y1="{high_y1:.1f}" x2="{high_x2:.1f}" y2="{high_y2:.1f}" stroke="{color}" stroke-width="2.2" />
  <line x1="{low_x1:.1f}" y1="{low_y1:.1f}" x2="{low_x2:.1f}" y2="{low_y2:.1f}" stroke="{color}" stroke-width="2.2" />"""
        return svg, label_svg(min(high_y1, high_y2) - 8)

    return "", ""


def news_link(item: NewsItem) -> str:
    title = html.escape(item.title)
    if not item.link:
        return title
    return f'<a href="{html.escape(item.link, quote=True)}">{title}</a>'


def resolve_symbols(args: argparse.Namespace) -> list[str]:
    symbols: list[str] = []
    if args.symbols:
        symbols.extend(args.symbols)
    elif args.watchlist:
        symbols.extend(WATCHLISTS[args.watchlist])
    seen: set[str] = set()
    unique: list[str] = []
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def resolve_universe(args: argparse.Namespace) -> tuple[list[str], dict[str, str]]:
    symbols = resolve_symbols(args)
    names: dict[str, str] = {}
    if symbols:
        return symbols, names

    if args.universe == "liquid":
        return LIQUID_OPTIONS_UNIVERSE[: args.max_symbols] if args.max_symbols else LIQUID_OPTIONS_UNIVERSE, names

    print("Downloading broad US common-stock universe...")
    universe = fetch_market_universe()
    if args.max_symbols:
        universe = universe[: args.max_symbols]
    names = {item.symbol: item.name for item in universe}
    return [item.symbol for item in universe], names


def passes_filters(item: Analysis, args: argparse.Namespace) -> bool:
    if item.price < args.min_price:
        return False
    if args.mode == "trade":
        if args.strategy != "patterns" and (item.setup_score is None or item.setup_score < args.min_setup_score):
            return False
        if args.direction == "calls" and item.setup_direction != "CALL":
            return False
        if args.direction == "puts" and item.setup_direction != "PUT":
            return False
        if item.average_dollar_volume is not None and item.average_dollar_volume < args.min_dollar_volume:
            return False
        if args.strategy != "patterns" and item.volume_ratio is not None and item.volume_ratio < args.min_volume_ratio:
            return False
        if item.return_20d is not None:
            if args.strategy == "breakout":
                if item.setup_direction == "CALL" and item.return_20d < args.min_20d_return:
                    return False
                if item.setup_direction == "PUT" and item.return_20d > -args.min_20d_return:
                    return False
            elif args.strategy == "reversal":
                if args.min_reversal_move > 0 and item.setup_direction == "CALL" and item.return_20d > -args.min_reversal_move:
                    return False
                if args.min_reversal_move > 0 and item.setup_direction == "PUT" and item.return_20d < args.min_reversal_move:
                    return False
        if args.trade_require_uptrend:
            if item.setup_direction == "CALL" and not (item.sma_50 and item.sma_200 and item.price > item.sma_50 > item.sma_200):
                return False
            if item.setup_direction == "PUT" and not (item.sma_50 and item.sma_200 and item.price < item.sma_50 < item.sma_200):
                return False
        return True
    if item.return_1y is not None and item.return_1y < args.min_1y_return:
        return False
    if item.return_6m is not None and item.return_6m < args.min_6m_return:
        return False
    if item.volatility is not None and item.volatility > args.max_volatility:
        return False
    if item.max_drawdown is not None and item.max_drawdown < -args.max_drawdown:
        return False
    if args.require_uptrend and not (item.sma_50 and item.sma_200 and item.price > item.sma_50 > item.sma_200):
        return False
    if args.exclude_overbought and item.rsi is not None and item.rsi > 70:
        return False
    if item.average_dollar_volume is not None and item.average_dollar_volume < args.min_dollar_volume:
        return False
    return True


def on_demand_enabled(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "single", False) and getattr(args, "symbols", []))


def add_on_demand_filter_note(item: Analysis, args: argparse.Namespace) -> None:
    if passes_filters(item, args):
        return
    note = "on-demand review: this ticker is shown even though it is below one or more normal scanner thresholds"
    notes = list(item.setup_notes or item.notes or [])
    if note not in notes:
        notes.insert(0, note)
    item.setup_notes = notes


def average_dollar_volume(series: PriceSeries, window: int = 30) -> float | None:
    if not series.closes or not series.volumes:
        return None
    closes = series.closes[-window:]
    volumes = series.volumes[-window:]
    if not closes or not volumes:
        return None
    values = [close * volume for close, volume in zip(closes, volumes)]
    return statistics.fmean(values)


def maybe_print_progress(index: int, total: int, kept: int, started_at: float, every: int) -> None:
    if not every or (index % every != 0 and index != total):
        return
    elapsed = time.monotonic() - started_at
    seconds_per_symbol = elapsed / index
    remaining = seconds_per_symbol * (total - index)
    print(
        f"Screened {index}/{total} symbols; "
        f"{kept} candidates kept; "
        f"elapsed {format_duration(elapsed)}; "
        f"ETA {format_duration(remaining)}",
        flush=True,
    )


def run(args: argparse.Namespace) -> int:
    args.catalyst_weight = clamp(args.catalyst_weight, 0.0, 1.0)
    args.market_regime = {"available": False, "bullish": True, "bearish": False, "label": "market regime unavailable"}
    if args.mode == "trade" and args.strategy == "patterns":
        return run_pattern_scan(args)
    if args.mode == "trade" and args.strategy == "reversal" and args.profit_filters:
        print("Checking SPY/QQQ market regime for optimized reversal filters...")
        args.market_regime = market_regime()
        print(f"Market regime: {args.market_regime.get('label')}")
    symbols, universe_names = resolve_universe(args)
    if not symbols:
        print("No symbols found. Pass symbols like AAPL MSFT NVDA or use --watchlist core.", file=sys.stderr)
        return 2

    quotes: dict[str, Quote] = {}
    if not args.skip_quotes:
        print(f"Fetching quote data for {len(symbols)} symbols...")
        try:
            quotes = fetch_quotes(symbols)
        except Exception as exc:
            print(f"Quote lookup failed, continuing with price-only analysis: {exc}", file=sys.stderr)

    results: list[Analysis] = []
    failed: list[str] = []
    started_at = time.monotonic()
    for index, symbol in enumerate(symbols, start=1):
        try:
            series = fetch_price_series(symbol)
            news_items: list[NewsItem] = []
            quote = quotes.get(symbol)
            if quote is None and symbol in universe_names:
                quote = Quote(symbol=symbol, name=universe_names[symbol])
            item = analyze(series, quote, args.profile, args.strategy, news_items)
            if on_demand_enabled(args):
                add_on_demand_filter_note(item, args)
            elif not passes_filters(item, args):
                maybe_print_progress(index, len(symbols), len(results), started_at, args.progress)
                continue
            results.append(item)
            results.sort(key=lambda result: rank_score(result, args.mode), reverse=True)
            if len(results) > args.keep:
                results = results[: args.keep]
        except Exception as exc:
            failed.append(f"{symbol} ({exc})")
            if args.verbose:
                print(f"Skipped {symbol}: {exc}", file=sys.stderr)
        maybe_print_progress(index, len(symbols), len(results), started_at, args.progress)

    if not results:
        if args.mode == "trade" and args.strategy == "patterns":
            print("No validated pattern found", file=sys.stderr)
            output = Path(args.output)
            write_report([], output, args.profile, failed)
            print(f"\nReport written to {output.resolve()}")
            print("Reminder: this is a screening model, not personalized investment advice.")
            return 0
        print("No symbols could be analyzed.", file=sys.stderr)
        return 1

    results.sort(key=lambda item: rank_score(item, args.mode), reverse=True)
    macro_news: list[NewsItem] = []
    macro_shock: dict[str, float | bool | str] | None = None
    if args.news or args.catalysts:
        print("Checking major market/geopolitical headlines...")
        macro_news = fetch_macro_news() if args.catalysts else []
        macro_shock = macro_oil_shock(macro_news)
        if macro_shock.get("active"):
            evidence = str(macro_shock.get("evidence") or "")
            print(f"Macro shock detected: {macro_shock.get('label')} - {evidence}")
            args.market_regime = {
                **args.market_regime,
                "available": True,
                "bullish": False,
                "bearish": True,
                "oil_shock": True,
                "oil_shock_score": float(macro_shock.get("score") or 0.0),
                "oil_shock_evidence": evidence,
                "label": str(macro_shock.get("label") or "oil/geopolitical shock"),
            }
        print(f"Checking recent headlines for {min(len(results), args.keep)} candidates...")
        deep_research_budget = min(len(results), max(args.limit, 25))
        for research_index, item in enumerate(results[: args.keep]):
            try:
                item.news = fetch_news(item.symbol, limit=40)
                try:
                    if research_index < deep_research_budget:
                        item.news = dedupe_news(fetch_deep_research_news(item.symbol, item.name) + item.news)
                except Exception:
                    pass
            except Exception as exc:
                print(f"News unavailable for {item.symbol}: {exc}", file=sys.stderr)
                item.news = []
            item.macro_news = macro_news
            if args.catalysts:
                apply_catalyst_assessment(item, args.catalyst_weight, macro_shock)
        if args.mode == "trade" and args.catalysts and args.require_catalyst_backing and not on_demand_enabled(args):
            before = len(results)
            results = [item for item in results if (item.catalyst_score or 0.0) >= args.min_catalyst_score]
            removed = before - len(results)
            if removed:
                print(f"Filtered out {removed} candidates without enough fresh catalyst backing.")
        results.sort(key=lambda item: rank_score(item, args.mode), reverse=True)

    chart_candidates = results[: args.keep] if args.mode == "trade" and args.strategy == "patterns" else results[: args.limit]
    print(f"Fetching 4-hour and 15-minute chart data for {len(chart_candidates)} report candidates...")
    chart_filtered: list[Analysis] = []
    for item in chart_candidates:
        four_hour_ok = True
        try:
            labels, opens, highs, lows, closes, volumes = fetch_four_hour_ohlcv(item.symbol)
            item.four_hour_dates = labels
            item.four_hour_opens = opens
            item.four_hour_highs = highs
            item.four_hour_lows = lows
            item.four_hour_closes = closes
            item.four_hour_volumes = volumes
            four_hour_ok = apply_four_hour_pattern_confirmation(item)
        except Exception as exc:
            four_hour_ok = item.setup_strategy != "patterns"
            if args.verbose:
                print(f"4-hour chart unavailable for {item.symbol}: {exc}", file=sys.stderr)
        if not four_hour_ok:
            if args.verbose:
                print(f"Skipped {item.symbol}: No validated pattern found", file=sys.stderr)
            continue
        try:
            labels, opens, highs, lows, closes, volumes = fetch_intraday_ohlcv(item.symbol)
            item.intraday_dates = labels
            item.intraday_opens = opens
            item.intraday_highs = highs
            item.intraday_lows = lows
            item.intraday_closes = closes
            item.intraday_volumes = volumes
            apply_intraday_confirmation(item)
        except Exception as exc:
            if args.verbose:
                print(f"15-minute chart unavailable for {item.symbol}: {exc}", file=sys.stderr)
        chart_filtered.append(item)
    if args.mode == "trade" and args.strategy == "patterns":
        results = chart_filtered
        if not results:
            print("No validated pattern found", file=sys.stderr)
            output = Path(args.output)
            write_report([], output, args.profile, failed)
            print(f"\nReport written to {output.resolve()}")
            print("Reminder: this is a screening model, not personalized investment advice.")
            return 0
    results.sort(key=lambda item: rank_score(item, args.mode), reverse=True)

    option_fallbacks: list[str] = []
    if args.mode == "trade" and args.options:
        for item in results[: args.limit]:
            try:
                item.option = fetch_option_contract(
                    item.symbol,
                    item.setup_direction or "CALL",
                    item.price,
                    args.min_dte,
                    args.max_dte,
                    args.options_provider,
                )
                if item.option is None:
                    item.option = estimate_option_contract(item.symbol, item.setup_direction or "CALL", item.price, args.min_dte)
                    option_fallbacks.append(f"{item.symbol} (no usable option chain rows)")
            except Exception as exc:
                item.option = estimate_option_contract(item.symbol, item.setup_direction or "CALL", item.price, args.min_dte)
                option_fallbacks.append(f"{item.symbol} ({exc})")
        if option_fallbacks:
            print(
                f"Live option chains from {args.options_provider} were unavailable for "
                f"{len(option_fallbacks)} symbols, so estimated contract structures were used. "
                "Try --options-provider tradier with TRADIER_TOKEN for a more reliable source, or run with --no-options to skip contract lookup.",
                file=sys.stderr,
            )
    if args.mode == "trade":
        for item in results[: args.limit]:
            item.trade_brief = build_trade_brief(item, args.market_regime)
            item.normalized_events = normalize_events_for_item(item)
            item.opportunity_rejection = opportunity_rejection_engine(item)
            item.options_opportunity = build_options_opportunity_score(item)
            trader_score = float(real_money_trader_judgment(item, item.trade_brief)["score"])
            item.final_trade_score = min(item.trade_brief.confidence_score, trader_score)
        before = min(len(results), args.limit)
        results = [item for item in results[: args.limit] if is_report_candidate(item)]
        removed = before - len(results)
        if removed:
            print(f"Filtered out {removed} setups that were not report-worthy after the final quality screen.")
        results.sort(key=lambda item: rank_score(item, args.mode), reverse=True)
    print()
    print_table(results, args.limit)
    output = Path(args.output)
    write_report(results[: args.limit], output, args.profile, failed)
    if args.notify:
        sent = maybe_send_trade_alerts(results[: args.limit], output)
        if sent:
            print(f"Sent {sent} Telegram trade alert(s).")
        elif telegram_configured():
            print("No watched setup upgraded into an entry condition.")
    print(f"\nReport written to {output.resolve()}")
    print("Reminder: this is a screening model, not personalized investment advice.")
    return 0


def normalize_on_demand_symbol(raw_symbol: str) -> str:
    symbol = raw_symbol.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,11}", symbol):
        raise ValueError("Enter a valid ticker symbol, for example NVDA or BRK.B.")
    return symbol


def market_status_header_html(snapshot: dict[str, Any]) -> str:
    status = str(snapshot.get("market_status") or "Markets are unavailable")
    state_class = "" if snapshot.get("market_open") else " is-closed"
    return f"""<header class="MarketStatusHeader market-status-header">
      <h1>Watchlist</h1>
      <button class="ai-powered-pill" type="button" aria-label="AI powered">
        <span aria-hidden="true">✦</span> AI powered
      </button>
      <p class="ai-subhead"><span aria-hidden="true">✦</span> AI insights. Real-time markets.</p>
      <p class="market-open{state_class}" id="marketOpenRow"><span id="marketOpenDot" aria-hidden="true"></span> <span id="marketOpenText">{html.escape(status)}</span></p>
    </header>"""


def market_insight_card_html(snapshot: dict[str, Any]) -> str:
    trend = str(snapshot.get("trend") or "Neutral")
    strength = str(snapshot.get("strength") or "Unknown")
    volatility = str(snapshot.get("volatility") or "Unknown")
    vix = snapshot.get("vix")
    vix_text = f"VIX {float(vix):.1f}" if isinstance(vix, (int, float)) else "VIX unavailable"
    trend_class = trend.lower()
    volatility_class = volatility.lower()
    return f"""<section class="MarketInsightCard market-insight-card" aria-label="Market summary">
      <div class="market-insight">
        <div class="insight-icon trend-icon" aria-hidden="true">
          <svg viewBox="0 0 32 32"><path d="M6 22 L13 15l5 5 8-11"></path><path d="M20 9h6v6"></path></svg>
        </div>
        <div>
          <span>Market Trend</span>
          <strong id="marketTrendText" class="{html.escape(trend_class)}">{html.escape(trend)}</strong>
          <small>Strength: <span id="marketStrengthText">{html.escape(strength)}</span></small>
        </div>
      </div>
      <div class="market-divider" aria-hidden="true"></div>
      <div class="market-insight">
        <div class="insight-icon volatility-icon" aria-hidden="true">
          <svg viewBox="0 0 32 32"><path d="m18 3-9 14h7l-2 12 10-16h-7z"></path></svg>
        </div>
        <div>
          <span>Volatility</span>
          <strong id="marketVolatilityText" class="purple-text {html.escape(volatility_class)}">{html.escape(volatility)}</strong>
          <small id="marketVixText">{html.escape(vix_text)}</small>
        </div>
      </div>
    </section>"""


def stock_watchlist_card_html(symbol: str, name: str, sector: str, ai_rating: str, recommendation: str) -> str:
    rec_class = "call" if recommendation.upper() == "CALL" else "put"
    rating_class = ai_rating.lower().replace(" ", "-")
    logo_text = "".join(part[0] for part in symbol.split() if part)[:2] or symbol[:2]
    logo_src = f"/static/logos/{urllib.parse.quote(symbol.upper())}.png"
    why = {
        "ABNB": "Airbnb is here because travel demand and consumer-discretionary momentum can reprice quickly when buyers defend a clean pullback. I would treat it as a call idea only if price confirms demand instead of drifting with the broader tape.",
        "PANW": "Palo Alto Networks is here because cybersecurity remains one of the cleaner enterprise-tech themes, and the setup has enough catalyst support to stay on the live list. The trade still needs confirmation because high-quality software names can fade hard when risk appetite cools.",
        "BAC": "Bank of America is here as a put idea because banks remain sensitive to rates, credit expectations, and risk-off flows. If financials weaken while BAC rejects resistance, the setup has a clear bearish path; if buyers hold it, the idea should be left alone.",
    }.get(symbol, "This ticker is on the live list because Atlas found a tradable setup with defined risk and current market context.")
    return f"""<article class="StockWatchlistCard stock-card is-collapsed" data-symbol="{html.escape(symbol)}">
        <button class="stock-card-main" type="button" aria-label="Expand {html.escape(symbol)}">
          <div class="stock-logo logo-{html.escape(symbol.lower())}" aria-hidden="true">
            <img src="{html.escape(logo_src)}" alt="" loading="lazy" onerror="this.classList.add('is-missing')" />
            <span>{html.escape(logo_text)}</span>
          </div>
          <div class="stock-copy">
            <div class="stock-title-row">
              <h2>{html.escape(symbol)}</h2>
            </div>
            <p>{html.escape(name)}</p>
            <span class="sector-badge">{html.escape(sector)}</span>
            <span class="ai-rating {html.escape(rating_class)}"><span aria-hidden="true">★</span> AI Rating <strong>{html.escape(ai_rating)}</strong></span>
          </div>
          <div class="stock-actions">
            <span class="recommendation {rec_class}">{html.escape(recommendation.title())}</span>
            <span class="chevron" aria-hidden="true"></span>
          </div>
        </button>
        <div class="stock-card-detail">
          <div>
            <strong>Why is it on the list?</strong>
            <p>{html.escape(why)}</p>
            <a class="read-more-link" href="/app/detail?symbol={urllib.parse.quote(symbol)}">Read More</a>
          </div>
        </div>
      </article>"""


def app_detail_profile(symbol: str) -> dict[str, str]:
    profiles = {
        "ABNB": {
            "name": "Airbnb, Inc.",
            "sector": "Travel",
            "rating": "Strong",
            "recommendation": "Call",
            "stance": "Actionable on trigger",
            "thesis": "ABNB is a cleaner long-side watch because the travel tape can move quickly when consumer-discretionary risk appetite improves. The idea is not to chase a green open; the attractive version is buyers defending a pullback, then forcing short-term sellers to cover through the prior intraday supply area.",
            "entry": "Wait for price to hold above the current demand area on a 5m or 15m retest. The first acceptable trigger is a higher low with expanding volume; the stronger trigger is a reclaim of VWAP followed by a candle close through the nearest resistance shelf.",
            "option": "The call only makes sense if the selected contract is liquid and not stretched by a wide bid/ask spread. Prefer a near-the-money strike with enough time for a two-to-five trading day move instead of a contract that needs an immediate breakout to survive theta.",
            "risk": "The main risk is that travel and consumer names lose sponsorship if the broader market turns defensive. If ABNB cannot hold the defended zone after entry, the trade loses its reason to exist quickly.",
            "invalidation": "Pass if buyers fail to defend the pullback, if the breakout candle fades back under VWAP, or if the option spread becomes too wide to exit cleanly.",
        },
        "PANW": {
            "name": "Palo Alto Networks",
            "sector": "Cybersecurity",
            "rating": "Moderate",
            "recommendation": "Call",
            "stance": "Watch for confirmation",
            "thesis": "PANW stays on the list because cybersecurity remains a durable enterprise-spending theme and buyers often defend quality software names when the market is willing to pay for growth. The setup is good enough to track, but not good enough to blindly buy without confirmation.",
            "entry": "Look for a controlled pullback that stops making lower lows, then wait for the 5m or 15m chart to reclaim VWAP with buyers stepping in above the prior reaction low. I would not force the trade if the first move of the day is a straight gap into resistance.",
            "option": "A call contract should be close enough to the money to respond to a moderate move, with expiration far enough out to avoid needing a same-day expansion. If premium is inflated or the spread is loose, the stock can be right while the contract is still wrong.",
            "risk": "The weakness is valuation sensitivity. If mega-cap tech or software loses momentum, PANW can look technically fine and still fail because the market is rotating away from the group.",
            "invalidation": "Drop the idea if price rejects the reclaim area twice, if software peers weaken at the same time, or if the trade starts requiring a perfect breakout to reach the first target.",
        },
        "BAC": {
            "name": "Bank of America",
            "sector": "Banking",
            "rating": "Hold",
            "recommendation": "Put",
            "stance": "Conditional put watch",
            "thesis": "BAC is a bearish watch because banks can reprice fast when rate expectations, credit concerns, or risk-off flows pressure financials. The setup is only useful if the broader financial tape confirms weakness instead of buyers rotating into banks as a defensive value trade.",
            "entry": "The put trigger needs rejection from resistance or a clean break under the nearest support area with weak reclaim attempts. A starter entry can work near resistance, but only if sellers are clearly controlling the tape on lower timeframes.",
            "option": "Use a put contract that is liquid enough to enter and exit without giving up too much edge. Avoid far out-of-the-money contracts unless the breakdown is already confirmed and momentum is expanding.",
            "risk": "The biggest risk is a sudden rates or macro shift that helps banks. BAC can reverse sharply if yields move in its favor or if financials catch a broad bid.",
            "invalidation": "Do not stay bearish if BAC reclaims resistance, if XLF strengthens while BAC holds support, or if the put spread is too wide to manage the trade tightly.",
        },
    }
    return profiles.get(
        symbol,
        {
            "name": symbol,
            "sector": "Market",
            "rating": "Watch",
            "recommendation": "Call",
            "stance": "Needs confirmation",
            "thesis": f"{symbol} is on the detail screen because it was selected from the Atlas watchlist flow. Treat it as a monitored setup until the live scanner confirms a cleaner entry trigger.",
            "entry": "Wait for price to confirm direction on the lower timeframe instead of entering because the ticker is visible. The cleaner setup is a defended level, a reclaim, or a breakdown with follow-through depending on the listed direction.",
            "option": "Use only liquid contracts with a manageable spread and enough time for the expected swing. If the contract quality is poor, skip the trade even if the chart looks workable.",
            "risk": "The risk is incomplete confirmation. A ticker can look interesting but still be a poor trade if market context, liquidity, or timing does not line up.",
            "invalidation": "Avoid the setup if price fails the trigger area, if the thesis depends on stale news, or if the option structure makes the risk/reward unattractive.",
        },
    )


def app_detail_html(symbol: str, market_snapshot: dict[str, Any] | None = None) -> str:
    profile = app_detail_profile(symbol)
    snapshot = market_snapshot or dashboard_market_snapshot()
    recommendation = profile["recommendation"]
    rec_class = "call" if recommendation.upper() == "CALL" else "put"
    status = str(snapshot.get("market_status") or "Market status unavailable")
    status_class = "" if snapshot.get("market_open") else " closed"
    sections = [
        ("Thesis", profile["thesis"]),
        ("Entry Logic", profile["entry"]),
        ("Option Focus", profile["option"]),
        ("Risk", profile["risk"]),
        ("What Changes My Mind", profile["invalidation"]),
    ]
    section_html = "\n".join(
        f"""<article class="detail-card">
          <span>{html.escape(title)}</span>
          <p>{html.escape(body)}</p>
        </article>"""
        for title, body in sections
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ATLAS | {html.escape(symbol)}</title>
  <link rel="icon" href="/atlas_wordmark.jpg">
  <style>
    :root {{
      color-scheme: dark;
      font-family: Inter, "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif;
      --bg: #020305;
      --card: rgba(12, 14, 20, .72);
      --line: rgba(255,255,255,.12);
      --muted: rgba(235,237,244,.62);
      --text: #f7f8fb;
      --green: #21f66b;
      --purple: #b34cff;
      --orange: #ff6a34;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; min-height: 100%; background: #000; color: var(--text); }}
    body {{
      background:
        radial-gradient(circle at 78% 8%, rgba(179,76,255,.20), transparent 31%),
        radial-gradient(circle at 48% -8%, rgba(33,246,107,.18), transparent 30%),
        linear-gradient(180deg, #030406 0%, #000 100%);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: -22% -35% auto 20%;
      height: 390px;
      pointer-events: none;
      background: linear-gradient(112deg, transparent 20%, rgba(33,246,107,.28), rgba(60,145,255,.15), rgba(179,76,255,.34), transparent 74%);
      filter: blur(30px);
      opacity: .76;
      transform: rotate(-8deg);
    }}
    a {{ color: inherit; text-decoration: none; }}
    .detail-shell {{
      position: relative;
      z-index: 1;
      width: min(850px, 100%);
      max-width: 850px;
      min-height: 100dvh;
      margin: 0 auto;
      padding: max(34px, env(safe-area-inset-top)) 26px calc(34px + env(safe-area-inset-bottom));
      overflow: auto;
    }}
    .back-link {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 30px;
      color: var(--muted);
      font-size: 15px;
      letter-spacing: .12em;
      text-transform: uppercase;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: start;
      margin-bottom: 24px;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--green);
      font-size: 16px;
      margin-bottom: 14px;
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 99px;
      background: var(--green);
      box-shadow: 0 0 18px rgba(33,246,107,.8);
    }}
    .dot.closed {{ background: var(--orange); box-shadow: 0 0 18px rgba(255,106,52,.7); }}
    h1 {{
      margin: 0;
      font-size: clamp(58px, 15vw, 96px);
      line-height: .86;
      letter-spacing: -.075em;
    }}
    .company {{
      margin: 12px 0 0;
      color: var(--muted);
      font-size: clamp(20px, 4.8vw, 28px);
      letter-spacing: -.04em;
    }}
    .direction {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 88px;
      height: 46px;
      border-radius: 12px;
      border: 1px solid rgba(33,246,107,.55);
      color: var(--green);
      font-size: 18px;
      font-weight: 780;
      letter-spacing: .02em;
      background: rgba(33,246,107,.08);
      box-shadow: inset 0 0 16px rgba(33,246,107,.06);
    }}
    .direction.put {{ border-color: rgba(255,106,52,.62); color: var(--orange); background: rgba(255,106,52,.08); }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 18px;
    }}
    .metric, .detail-card {{
      border: 1px solid var(--line);
      background: linear-gradient(145deg, rgba(17,20,28,.72), rgba(4,5,9,.54));
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.04), 0 22px 60px rgba(0,0,0,.30);
    }}
    .metric {{
      border-radius: 18px;
      padding: 16px;
    }}
    .metric span, .detail-card span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .16em;
      text-transform: uppercase;
    }}
    .metric strong {{
      display: block;
      margin-top: 9px;
      font-size: 20px;
      letter-spacing: -.04em;
    }}
    .detail-grid {{
      display: grid;
      gap: 14px;
    }}
    .detail-card {{
      border-radius: 22px;
      padding: 22px;
    }}
    .detail-card p {{
      margin: 13px 0 0;
      color: rgba(245,246,250,.82);
      font-size: 17px;
      line-height: 1.55;
      letter-spacing: -.025em;
    }}
    .footer-actions {{
      display: grid;
      grid-template-columns: 1fr;
      margin-top: 18px;
    }}
    .primary-link {{
      min-height: 54px;
      border-radius: 16px;
      border: 1px solid rgba(33,246,107,.45);
      color: var(--green);
      display: grid;
      place-items: center;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: .18em;
      text-transform: uppercase;
      background: rgba(33,246,107,.06);
    }}
    @media (max-width: 560px) {{
      .detail-shell {{ padding-left: 20px; padding-right: 20px; }}
      .hero {{ grid-template-columns: 1fr; }}
      .direction {{ justify-self: start; }}
      .summary-grid {{ grid-template-columns: 1fr; }}
      .detail-card {{ padding: 20px; }}
      .detail-card p {{ font-size: 16px; }}
    }}
  </style>
</head>
<body>
  <main class="detail-shell">
    <a class="back-link" href="/app">← Back to Watchlist</a>
    <section class="hero">
      <div>
        <div class="eyebrow"><span class="dot{html.escape(status_class)}"></span>{html.escape(status)}</div>
        <h1>{html.escape(symbol)}</h1>
        <p class="company">{html.escape(profile["name"])}</p>
      </div>
      <span class="direction {rec_class}">{html.escape(recommendation)}</span>
    </section>
    <section class="summary-grid" aria-label="Trade summary">
      <div class="metric"><span>Stance</span><strong>{html.escape(profile["stance"])}</strong></div>
      <div class="metric"><span>Sector</span><strong>{html.escape(profile["sector"])}</strong></div>
      <div class="metric"><span>AI Rating</span><strong>{html.escape(profile["rating"])}</strong></div>
    </section>
    <section class="detail-grid" aria-label="Trade detail">
      {section_html}
    </section>
    <div class="footer-actions">
      <a class="primary-link" href="/app">Return to Watchlist</a>
    </div>
  </main>
</body>
</html>"""


def bottom_nav_html() -> str:
    return """<nav class="BottomNav bottom-nav" aria-label="ATLAS navigation">
      <button class="nav-item is-active" type="button" data-panel="watchlist" aria-label="Watchlist">
        <svg class="nav-icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M9 8h18"></path><path d="M9 16h18"></path><path d="M9 24h18"></path><circle cx="4.5" cy="8" r="1.4"></circle><circle cx="4.5" cy="16" r="1.4"></circle><circle cx="4.5" cy="24" r="1.4"></circle></svg>
        <span>Watchlist</span>
      </button>
      <button class="nav-item" type="button" data-panel="news" aria-label="News">
        <svg class="nav-icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M8 5h14l4 4v18H8z"></path><path d="M22 5v6h6"></path><path d="M12 15h10"></path><path d="M12 20h10"></path></svg>
        <span>News</span>
      </button>
      <button class="nav-item" type="button" data-panel="search" aria-label="Search">
        <svg class="nav-icon" viewBox="0 0 32 32" aria-hidden="true"><circle cx="14" cy="14" r="9"></circle><path d="m21 21 7 7"></path></svg>
        <span>Search</span>
      </button>
      <button class="nav-item" type="button" data-panel="profile" aria-label="Profile">
        <svg class="nav-icon" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="10.5" r="4"></circle><path d="M8 27c1.5-6 5-9 8-9s6.5 3 8 9"></path></svg>
        <span>Profile</span>
      </button>
    </nav>"""


def report_dashboard_html(market_snapshot: dict[str, Any] | None = None) -> str:
    market_snapshot = market_snapshot or dashboard_market_snapshot()
    stock_cards = "\n".join(
        [
            stock_watchlist_card_html("ABNB", "Airbnb, Inc.", "Travel", "Strong", "Call"),
            stock_watchlist_card_html("PANW", "Palo Alto Networks", "Cybersecurity", "Moderate", "Call"),
            stock_watchlist_card_html("BAC", "Bank of America", "Banking", "Hold", "Put"),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ATLAS</title>
  <link rel="icon" href="/atlas_wordmark.jpg">
  <style>
    :root {{
      color-scheme: dark;
      font-family: Inter, "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif;
      --bg: #020305;
      --card: rgba(11, 13, 18, .70);
      --card-strong: rgba(16, 18, 25, .78);
      --line: rgba(255, 255, 255, .12);
      --muted: rgba(230, 233, 241, .66);
      --text: #f8f8fb;
      --green: #21f66b;
      --green-soft: rgba(33, 246, 107, .16);
      --purple: #b34cff;
      --orange: #ff6a34;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ min-height: 100%; background: #000; }}
    body {{
      margin: 0;
      min-height: 100vh;
      height: 100dvh;
      background:
        radial-gradient(circle at 72% 12%, rgba(144, 64, 255, .18), transparent 30%),
        radial-gradient(circle at 55% 0%, rgba(15, 245, 119, .15), transparent 25%),
        linear-gradient(180deg, #040506 0%, #000104 100%);
      color: var(--text);
      overflow: hidden;
      overscroll-behavior: none;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: -22% -34% auto 22%;
      height: 380px;
      pointer-events: none;
      background:
        linear-gradient(112deg, transparent 20%, rgba(22, 245, 130, .34), rgba(20, 151, 255, .18), rgba(168, 62, 255, .42), transparent 74%);
      filter: blur(28px);
      opacity: .72;
      transform: rotate(-8deg);
    }}
    body::after {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        radial-gradient(circle at 50% 36%, rgba(255, 255, 255, .035), transparent 1px),
        linear-gradient(rgba(255, 255, 255, .012) 1px, transparent 1px);
      background-size: 100% 100%, 100% 5px;
      opacity: .28;
      mix-blend-mode: screen;
    }}
    a {{ color: inherit; text-decoration: none; }}
    button {{ font: inherit; color: inherit; }}
    .is-hidden {{ display: none !important; }}
    .app-shell {{
      position: relative;
      z-index: 1;
      height: 100dvh;
      max-width: 850px;
      margin: 0 auto;
      padding: max(34px, env(safe-area-inset-top)) 42px calc(106px + env(safe-area-inset-bottom));
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      overflow: auto;
      overscroll-behavior: contain;
    }}
    .market-status-header {{
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: start;
      gap: 18px;
      padding-top: 56px;
      margin-bottom: 20px;
    }}
    .market-status-header h1 {{
      margin: 0 0 14px;
      font-size: clamp(54px, 10vw, 76px);
      line-height: .88;
      letter-spacing: -.065em;
      font-weight: 780;
    }}
    .ai-subhead, .market-open {{
      display: flex;
      align-items: center;
      gap: 11px;
      margin: 0 0 13px;
      color: var(--muted);
      font-size: clamp(20px, 4vw, 26px);
      line-height: 1.15;
      letter-spacing: -.035em;
      font-weight: 520;
    }}
    .ai-subhead, .market-open {{ grid-column: 1 / -1; }}
    .ai-subhead span {{ color: var(--purple); text-shadow: 0 0 18px rgba(179, 76, 255, .9); }}
    .market-open {{ color: var(--green); }}
    .market-open #marketOpenDot {{
      width: 18px;
      height: 18px;
      border-radius: 999px;
      background: var(--green);
      box-shadow: 0 0 24px rgba(33, 246, 107, .72);
    }}
    .market-open.is-closed {{ color: var(--orange); }}
    .market-open.is-closed #marketOpenDot {{
      background: var(--orange);
      box-shadow: 0 0 24px rgba(255, 106, 52, .55);
    }}
    .ai-powered-pill {{
      margin-top: 16px;
      min-height: 58px;
      padding: 0 21px;
      border-radius: 13px;
      border: 1px solid rgba(196, 77, 255, .64);
      background: rgba(35, 15, 48, .28);
      color: #d68cff;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: 20px;
      letter-spacing: -.02em;
      white-space: nowrap;
      box-shadow: inset 0 0 22px rgba(179, 76, 255, .08), 0 0 26px rgba(179, 76, 255, .18);
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
    }}
    .ai-powered-pill span {{ text-shadow: 0 0 16px rgba(179, 76, 255, .9); }}
    .market-insight-card {{
      display: grid;
      grid-template-columns: 1fr 1px 1fr;
      align-items: center;
      min-height: 145px;
      padding: 26px 28px;
      border: 1px solid var(--line);
      border-radius: 25px;
      background: linear-gradient(145deg, rgba(17, 20, 28, .72), rgba(5, 6, 10, .46));
      box-shadow: inset 0 1px 0 rgba(255,255,255,.05), 0 22px 70px rgba(0,0,0,.42);
      backdrop-filter: blur(28px);
      -webkit-backdrop-filter: blur(28px);
      margin-bottom: 22px;
    }}
    .market-insight {{
      display: grid;
      grid-template-columns: 75px 1fr;
      align-items: center;
      gap: 20px;
      min-width: 0;
    }}
    .market-divider {{ width: 1px; height: 92px; background: rgba(255,255,255,.13); }}
    .insight-icon {{
      width: 75px;
      height: 75px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      border: 1px solid rgba(255,255,255,.10);
      background: rgba(255,255,255,.035);
    }}
    .trend-icon {{ color: var(--green); background: rgba(33,246,107,.12); box-shadow: 0 0 34px rgba(33,246,107,.14); }}
    .volatility-icon {{ color: var(--purple); background: rgba(179,76,255,.12); box-shadow: 0 0 34px rgba(179,76,255,.14); }}
    .insight-icon svg {{ width: 42px; height: 42px; fill: none; stroke: currentColor; stroke-width: 3.7; stroke-linecap: round; stroke-linejoin: round; }}
    .volatility-icon svg {{ fill: currentColor; stroke: none; }}
    .market-insight span, .market-insight small {{
      display: block;
      color: var(--muted);
      font-size: 17px;
      letter-spacing: -.02em;
    }}
    .market-insight strong {{
      display: block;
      color: var(--green);
      font-size: 27px;
      line-height: 1.15;
      margin: 7px 0 6px;
      letter-spacing: -.035em;
    }}
    .market-insight .purple-text {{ color: var(--purple); }}
    .market-insight strong.bearish, .market-insight strong.elevated, .market-insight strong.high {{ color: var(--orange); }}
    .market-insight strong.neutral, .market-insight strong.unknown {{ color: rgba(236,238,245,.70); }}
    .section-switcher {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      align-items: end;
      height: 70px;
      border-bottom: 1px solid rgba(255, 255, 255, .11);
      margin-bottom: 20px;
    }}
    .section-tab {{
      border: 0;
      background: transparent;
      color: rgba(236, 238, 245, .56);
      min-height: 70px;
      padding: 0 0 21px;
      font-size: 25px;
      font-weight: 710;
      letter-spacing: -.035em;
      text-align: center;
      cursor: pointer;
    }}
    .section-tab.is-active {{
      color: #fff;
      position: relative;
    }}
    .section-tab.is-active::after {{
      content: "";
      position: absolute;
      left: 22%;
      right: 22%;
      bottom: -1px;
      height: 2px;
      background: linear-gradient(90deg, transparent, var(--green), transparent);
      box-shadow: 0 0 18px rgba(33,246,107,.9);
    }}
    .content {{ flex: 1 0 auto; padding-bottom: 24px; }}
    .stock-list {{ display: grid; gap: 16px; }}
    .stock-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: linear-gradient(145deg, rgba(14, 16, 23, .78), rgba(5, 6, 10, .56));
      box-shadow: inset 0 1px 0 rgba(255,255,255,.035), 0 24px 60px rgba(0,0,0,.30);
      overflow: hidden;
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      transition: transform .24s ease, border-color .24s ease, background .24s ease;
    }}
    .stock-card:active {{ transform: scale(.992); }}
    .stock-card-main {{
      width: 100%;
      min-height: 170px;
      display: grid;
      grid-template-columns: 104px minmax(0, 1fr) 112px;
      gap: 24px;
      align-items: center;
      padding: 20px 24px;
      border: 0;
      background: transparent;
      text-align: left;
      cursor: pointer;
    }}
    .stock-logo {{
      width: 104px;
      height: 104px;
      border-radius: 18px;
      display: grid;
      place-items: center;
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(255,255,255,.12);
      background: rgba(255,255,255,.025);
      color: rgba(255,255,255,.92);
      font-size: 24px;
      font-weight: 780;
      letter-spacing: -.05em;
      box-shadow: inset 0 0 20px rgba(255,255,255,.025);
    }}
    .stock-logo img {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: contain;
      padding: 18px;
      background: rgba(255,255,255,.018);
      opacity: 1;
      transition: opacity .18s ease;
    }}
    .stock-logo img.is-missing {{
      opacity: 0;
      pointer-events: none;
    }}
    .stock-logo span {{
      position: relative;
      z-index: 1;
    }}
    .stock-logo img:not(.is-missing) + span {{
      opacity: 0;
    }}
    .logo-abnb {{ color: #ff315b; text-shadow: 0 0 22px rgba(255,49,91,.42); }}
    .logo-panw {{ color: #ff6419; text-shadow: 0 0 22px rgba(255,100,25,.42); }}
    .logo-bac {{ color: #ff3048; text-shadow: 0 0 22px rgba(255,48,72,.42); }}
    .stock-copy {{ min-width: 0; }}
    .stock-copy h2 {{
      margin: 0 0 4px;
      font-size: 31px;
      line-height: 1;
      letter-spacing: -.045em;
      font-weight: 760;
    }}
    .stock-copy p {{
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 21px;
      line-height: 1.2;
      letter-spacing: -.035em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .sector-badge {{
      display: table;
      color: #d46cff;
      border: 1px solid rgba(179, 76, 255, .18);
      background: rgba(179, 76, 255, .08);
      border-radius: 8px;
      padding: 2px 9px 4px;
      font-size: 18px;
      letter-spacing: -.035em;
      margin-bottom: 13px;
    }}
    .ai-rating {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
      color: rgba(244, 245, 250, .82);
      background: rgba(255,255,255,.045);
      border: 1px solid rgba(255,255,255,.055);
      border-radius: 10px;
      padding: 7px 13px;
      font-size: 18px;
      letter-spacing: -.035em;
    }}
    .ai-rating span {{ color: var(--green); filter: drop-shadow(0 0 8px rgba(33,246,107,.65)); }}
    .ai-rating strong {{ color: var(--green); font-weight: 600; }}
    .ai-rating.hold span, .ai-rating.hold strong {{ color: var(--orange); filter: drop-shadow(0 0 8px rgba(255,106,52,.55)); }}
    .stock-actions {{
      align-self: stretch;
      display: grid;
      align-content: center;
      justify-items: end;
      gap: 36px;
    }}
    .recommendation {{
      display: inline-grid;
      place-items: center;
      min-width: 84px;
      min-height: 45px;
      border-radius: 9px;
      font-size: 22px;
      font-weight: 680;
      letter-spacing: -.035em;
      border: 1px solid;
    }}
    .recommendation.call {{ color: var(--green); border-color: rgba(33,246,107,.50); background: rgba(33,246,107,.06); }}
    .recommendation.put {{ color: #ff793d; border-color: rgba(255,106,52,.62); background: rgba(255,106,52,.07); }}
    .chevron {{
      width: 18px;
      height: 18px;
      border-right: 3px solid rgba(255,255,255,.67);
      border-bottom: 3px solid rgba(255,255,255,.67);
      transform: rotate(45deg);
      transition: transform .28s ease;
      margin-right: 3px;
    }}
    .stock-card:not(.is-collapsed) .chevron {{ transform: rotate(225deg); }}
    .stock-card-detail {{
      display: grid;
      grid-template-rows: 1fr;
      opacity: 1;
      transition: grid-template-rows .32s cubic-bezier(.2,.8,.2,1), opacity .22s ease;
    }}
    .stock-card.is-collapsed .stock-card-detail {{
      grid-template-rows: 0fr;
      opacity: 0;
    }}
    .stock-card-detail > div {{
      min-height: 0;
      overflow: hidden;
      border-top: 1px solid rgba(255,255,255,.09);
      padding: 0 24px 24px 152px;
    }}
    .stock-card-detail strong {{
      display: block;
      margin: 20px 0 9px;
      font-size: 13px;
      letter-spacing: .18em;
      text-transform: uppercase;
    }}
    .stock-card-detail p {{
      margin: 0;
      color: rgba(236, 238, 245, .76);
      font-size: 17px;
      line-height: 1.5;
      letter-spacing: -.025em;
    }}
    .read-more-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      margin-top: 18px;
      padding: 0 18px;
      border-radius: 999px;
      border: 1px solid rgba(33,246,107,.42);
      color: var(--green);
      background: rgba(33,246,107,.06);
      font-size: 13px;
      font-weight: 720;
      letter-spacing: .12em;
      text-transform: uppercase;
    }}
    .panel-placeholder {{
      display: none;
      min-height: 280px;
      place-items: center;
      text-align: center;
      color: rgba(236,238,245,.64);
      border: 1px solid var(--line);
      border-radius: 24px;
      background: rgba(255,255,255,.035);
      padding: 24px;
    }}
    .panel-placeholder.is-active {{ display: grid; }}
    .bottom-nav {{
      position: fixed;
      left: 50%;
      bottom: max(14px, env(safe-area-inset-bottom));
      transform: translateX(-50%);
      width: min(760px, calc(100vw - 24px));
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      align-items: center;
      z-index: 5;
      padding: 11px 14px 10px;
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 30px;
      background: rgba(8, 10, 15, .72);
      backdrop-filter: blur(28px);
      -webkit-backdrop-filter: blur(28px);
      box-shadow: 0 -10px 48px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.04);
    }}
    .nav-item {{
      min-height: 62px;
      border: 0;
      background: transparent;
      color: rgba(235, 236, 242, .66);
      display: grid;
      place-items: center;
      align-content: center;
      gap: 5px;
      font-size: 13px;
      font-weight: 520;
      letter-spacing: -.025em;
      cursor: pointer;
    }}
    .nav-item.is-active {{ color: var(--green); }}
    .nav-icon {{
      width: 29px;
      height: 29px;
      display: block;
      fill: none;
      stroke: currentColor;
      stroke-width: 1.8;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    .status-probe {{
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }}
    @media (max-width: 720px) {{
      .app-shell {{
        padding: max(28px, env(safe-area-inset-top)) 30px calc(98px + env(safe-area-inset-bottom));
      }}
      .market-status-header {{ padding-top: 44px; gap: 13px 12px; margin-bottom: 18px; }}
      .market-status-header h1 {{ font-size: 57px; margin-bottom: 2px; letter-spacing: -.07em; }}
      .ai-subhead, .market-open {{ font-size: 19px; margin-bottom: 7px; gap: 9px; }}
      .market-open #marketOpenDot {{ width: 15px; height: 15px; }}
      .ai-powered-pill {{ min-height: 44px; padding: 0 13px; font-size: 15px; border-radius: 12px; }}
      .market-insight-card {{ min-height: 112px; padding: 17px 15px; border-radius: 20px; margin-bottom: 18px; }}
      .market-insight {{ grid-template-columns: 54px 1fr; gap: 12px; }}
      .insight-icon {{ width: 54px; height: 54px; }}
      .insight-icon svg {{ width: 30px; height: 30px; }}
      .market-insight strong {{ font-size: 21px; }}
      .market-insight span, .market-insight small {{ font-size: 14px; }}
      .market-divider {{ height: 70px; }}
      .section-switcher {{ height: 54px; margin-bottom: 14px; }}
      .section-tab {{ min-height: 54px; padding-bottom: 14px; font-size: 20px; }}
      .stock-list {{ gap: 14px; }}
      .stock-card-main {{
        min-height: 148px;
        grid-template-columns: 84px minmax(0, 1fr) 78px;
        gap: 16px;
        padding: 16px 20px;
      }}
      .stock-logo {{ width: 84px; height: 84px; border-radius: 15px; font-size: 20px; }}
      .stock-copy h2 {{ font-size: 28px; margin-bottom: 4px; }}
      .stock-copy p {{ font-size: 18px; margin-bottom: 8px; }}
      .sector-badge {{ font-size: 15px; margin-bottom: 11px; padding: 2px 8px 3px; }}
      .ai-rating {{ font-size: 14px; padding: 6px 10px; gap: 7px; }}
      .stock-actions {{ gap: 31px; }}
      .recommendation {{ min-width: 66px; min-height: 40px; font-size: 19px; }}
      .stock-card-detail > div {{ padding-left: 124px; }}
    }}
    @media (max-width: 390px) {{
      .app-shell {{ padding-left: 20px; padding-right: 20px; }}
      .market-status-header {{ padding-top: 42px; }}
      .market-status-header h1 {{ font-size: 48px; }}
      .ai-subhead, .market-open {{ font-size: 16px; }}
      .ai-powered-pill {{ min-height: 40px; padding: 0 11px; font-size: 13px; }}
      .market-insight-card {{ grid-template-columns: 1fr 1px 1fr; gap: 0; padding: 14px 13px; min-height: 100px; }}
      .market-insight {{ grid-template-columns: 44px 1fr; gap: 10px; }}
      .insight-icon {{ width: 44px; height: 44px; }}
      .insight-icon svg {{ width: 25px; height: 25px; }}
      .market-insight strong {{ font-size: 18px; }}
      .market-insight span, .market-insight small {{ font-size: 12px; }}
      .market-divider {{ display: block; height: 58px; }}
      .stock-card-main {{ min-height: 138px; grid-template-columns: 74px minmax(0, 1fr) 64px; gap: 14px; padding: 14px; }}
      .stock-logo {{ width: 74px; height: 74px; border-radius: 14px; font-size: 18px; }}
      .stock-copy h2 {{ font-size: 25px; }}
      .stock-copy p {{ font-size: 16px; }}
      .sector-badge {{ font-size: 13px; margin-bottom: 9px; }}
      .ai-rating {{ font-size: 12px; padding: 5px 8px; }}
      .recommendation {{ min-width: 58px; min-height: 36px; font-size: 17px; }}
      .chevron {{ width: 15px; height: 15px; border-width: 2px; }}
      .stock-card-detail > div {{ padding-left: 16px; padding-right: 16px; }}
    }}
  </style>
</head>
<body>
  <main class="app-shell" aria-label="ATLAS">
    {market_status_header_html(market_snapshot)}
    {market_insight_card_html(market_snapshot)}
    <nav class="section-switcher" aria-label="Watchlist groups">
      <button class="section-tab is-active" type="button" data-subpanel="live-watchlist">Live</button>
      <button class="section-tab" type="button" data-subpanel="custom-watchlist">Custom</button>
      <button class="section-tab" type="button" data-subpanel="alerts">Alerts</button>
    </nav>
    <section class="content">
      <section class="stock-list" data-subpanel-content="live-watchlist">
        {stock_cards}
      </section>
      <section class="panel-placeholder" data-subpanel-content="custom-watchlist">Custom Watchlist is ready for saved tickers.</section>
      <section class="panel-placeholder" data-subpanel-content="alerts">Ready-for-entry alerts and position updates will appear here.</section>
      <section class="panel-placeholder" data-panel-content="news">News will summarize market-moving headlines from the latest Atlas scan.</section>
      <section class="panel-placeholder" data-panel-content="search">Search will support ticker research and on-demand analysis.</section>
      <section class="panel-placeholder" data-panel-content="profile">Profile will hold account and notification settings.</section>
      <span class="status-probe" aria-live="polite">Status: <span id="appStatus">Online</span></span>
    </section>
    {bottom_nav_html()}
  </main>
  <script>
    const tabs = Array.from(document.querySelectorAll('.nav-item'));
    const sectionTabs = Array.from(document.querySelectorAll('.section-tab'));
    const sectionSwitcher = document.querySelector('.section-switcher');
    const subpanelContents = Array.from(document.querySelectorAll('[data-subpanel-content]'));
    const panelContents = Array.from(document.querySelectorAll('[data-panel-content]'));
    const stockCards = Array.from(document.querySelectorAll('.stock-card'));

    function showPanel(name) {{
      for (const tab of tabs) tab.classList.toggle('is-active', tab.dataset.panel === name);
      for (const content of panelContents) content.classList.toggle('is-active', content.dataset.panelContent === name);
      const showWatchlist = name === 'watchlist';
      sectionSwitcher?.classList.toggle('is-hidden', !showWatchlist);
      for (const content of subpanelContents) content.classList.toggle('is-hidden', !showWatchlist || content.dataset.subpanelContent !== activeSubpanelName());
    }}

    function showSubpanel(name) {{
      if (!name) return;
      for (const tab of sectionTabs) tab.classList.toggle('is-active', tab.dataset.subpanel === name);
      for (const content of subpanelContents) {{
        const isActive = content.dataset.subpanelContent === name;
        content.classList.toggle('is-hidden', !isActive);
        content.classList.toggle('is-active', isActive && content.classList.contains('panel-placeholder'));
      }}
    }}

    function activeSubpanelName() {{
      return sectionTabs.find((tab) => tab.classList.contains('is-active'))?.dataset.subpanel || 'live-watchlist';
    }}

    async function refreshStatus() {{
      const status = document.getElementById('appStatus');
      try {{
        const response = await fetch('/healthz', {{ cache: 'no-store' }});
        if (!response.ok) throw new Error('offline');
        status.textContent = 'Online';
      }} catch (error) {{
        status.textContent = 'Offline';
      }}
    }}

    async function refreshMarketStatus() {{
      try {{
        const response = await fetch('/api/market-status', {{ cache: 'no-store' }});
        if (!response.ok) throw new Error('market unavailable');
        const snapshot = await response.json();
        const openRow = document.getElementById('marketOpenRow');
        const openText = document.getElementById('marketOpenText');
        const trendText = document.getElementById('marketTrendText');
        const strengthText = document.getElementById('marketStrengthText');
        const volatilityText = document.getElementById('marketVolatilityText');
        const vixText = document.getElementById('marketVixText');
        if (openRow) openRow.classList.toggle('is-closed', !snapshot.market_open);
        if (openText) openText.textContent = snapshot.market_status || 'Markets unavailable';
        if (trendText) {{
          trendText.textContent = snapshot.trend || 'Neutral';
          trendText.className = String(snapshot.trend || 'neutral').toLowerCase();
        }}
        if (strengthText) strengthText.textContent = snapshot.strength || 'Unknown';
        if (volatilityText) {{
          volatilityText.textContent = snapshot.volatility || 'Unknown';
          volatilityText.className = `purple-text ${{String(snapshot.volatility || 'unknown').toLowerCase()}}`;
        }}
        if (vixText) vixText.textContent = typeof snapshot.vix === 'number' ? `VIX ${{snapshot.vix.toFixed(1)}}` : 'VIX unavailable';
      }} catch (error) {{
        const openText = document.getElementById('marketOpenText');
        if (openText) openText.textContent = 'Market data unavailable';
      }}
    }}

    for (const tab of tabs) tab.addEventListener('click', () => showPanel(tab.dataset.panel));
    for (const tab of sectionTabs) tab.addEventListener('click', () => showSubpanel(tab.dataset.subpanel));
    for (const card of stockCards) {{
      card.querySelector('.stock-card-main')?.addEventListener('click', () => card.classList.toggle('is-collapsed'));
    }}
    refreshStatus();
    refreshMarketStatus();
    setInterval(refreshStatus, 30000);
    setInterval(refreshMarketStatus, 60000);
  </script>
</body>
</html>"""


def scanner_command(script_path: Path, output_name: str) -> list[str]:
    return [
        sys.executable,
        str(script_path),
        "--mode",
        "trade",
        "--strategy",
        "reversal",
        "--direction",
        "both",
        "--no-profit-filters",
        "--min-price",
        "10",
        "--min-dollar-volume",
        "25000000",
        "--min-setup-score",
        "45",
        "--min-volume-ratio",
        "0.2",
        "--min-reversal-move",
        "0.0",
        "--require-catalyst-backing",
        "--min-catalyst-score",
        "55",
        "--catalyst-weight",
        "0.60",
        "--limit",
        "20",
        "--progress",
        "10",
        "--notify",
        "--output",
        output_name,
    ]


def on_demand_command(script_path: Path, symbol: str, output_name: str) -> list[str]:
    return [
        sys.executable,
        str(script_path),
        symbol,
        "--mode",
        "trade",
        "--strategy",
        "reversal",
        "--direction",
        "both",
        "--no-profit-filters",
        "--catalyst-weight",
        "0.60",
        "--single",
        "--limit",
        "1",
        "--output",
        output_name,
    ]


def legacy_detail_symbol(parsed: urllib.parse.ParseResult) -> str | None:
    """Map old detail-page URLs into the current in-report detail view."""
    path = parsed.path.strip("/")
    if path == "stock_details.html":
        params = urllib.parse.parse_qs(parsed.query)
        symbol = (params.get("symbol") or params.get("detail") or [""])[0]
        return re.sub(r"[^A-Za-z0-9_-]+", "", symbol.upper())
    match = re.fullmatch(r"stock_detail_([A-Za-z0-9_-]+)\.html", path)
    if match:
        return re.sub(r"[^A-Za-z0-9_-]+", "", match.group(1).upper())
    return None


class ReportRequestHandler(http.server.SimpleHTTPRequestHandler):
    server_version = "StockAnalystReport/1.0"

    def do_HEAD(self) -> None:
        if not self.is_authorized():
            self.request_auth()
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/app", "/dashboard"}:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if parsed.path in {"/healthz", "/api/market-status"}:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        super().do_HEAD()

    def do_GET(self) -> None:
        if not self.is_authorized():
            self.request_auth()
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/app", "/dashboard"}:
            self.send_html(report_dashboard_html())
            return
        if parsed.path == "/app/detail":
            params = urllib.parse.parse_qs(parsed.query)
            try:
                symbol = normalize_on_demand_symbol((params.get("symbol") or [""])[0])
            except ValueError:
                self.send_response(302)
                self.send_header("Location", "/app")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            self.send_html(app_detail_html(symbol))
            return
        legacy_symbol = legacy_detail_symbol(parsed)
        if legacy_symbol is not None:
            target = "/stock_report.html"
            if legacy_symbol:
                target = f"{target}?detail={urllib.parse.quote(legacy_symbol)}"
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if parsed.path in {"/analyze", "/api/analyze"}:
            self.handle_analyze(parsed)
            return
        if parsed.path == "/api/scan":
            self.handle_scan()
            return
        if parsed.path == "/api/test-alert":
            self.handle_test_alert()
            return
        if parsed.path in {"/api/test-trade-alerts", "/api/test-notifications"}:
            self.handle_test_trade_alerts()
            return
        if parsed.path == "/api/market-status":
            self.send_json(dashboard_market_snapshot(use_cache=False))
            return
        if parsed.path == "/healthz":
            self.send_json({"ok": True, "service": "stock-analyst"})
            return
        if parsed.path == "/":
            self.path = "/app"
            self.send_html(report_dashboard_html())
            return
        super().do_GET()

    def is_authorized(self) -> bool:
        password = os.environ.get("STOCK_ANALYST_PASSWORD")
        if not password:
            return True
        header = self.headers.get("Authorization", "")
        expected = "Basic " + base64.b64encode(f"stock:{password}".encode("utf-8")).decode("ascii")
        return header == expected

    def request_auth(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Stock Analyst"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Authentication required.")

    def handle_analyze(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        try:
            symbol = normalize_on_demand_symbol((params.get("symbol") or [""])[0])
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
            return

        output_name = "on_demand_report.html"
        script_path = Path(__file__).resolve()
        command = on_demand_command(script_path, symbol, output_name)
        try:
            completed = subprocess.run(
                command,
                cwd=script_path.parent,
                capture_output=True,
                text=True,
                timeout=240,
            )
        except subprocess.TimeoutExpired:
            self.send_json({"ok": False, "error": f"{symbol} analysis timed out after 4 minutes."}, status=504)
            return

        if completed.returncode != 0:
            error_text = (completed.stderr or completed.stdout or "Analysis failed.").strip().splitlines()
            self.send_json({"ok": False, "error": error_text[-1] if error_text else "Analysis failed."}, status=500)
            return

        self.send_json(
            {
                "ok": True,
                "symbol": symbol,
                "report_url": f"/{output_name}?t={int(time.time())}",
            }
        )

    def handle_scan(self) -> None:
        output_name = "stock_report.html"
        script_path = Path(__file__).resolve()
        command = scanner_command(script_path, output_name)
        if not SCAN_LOCK.acquire(blocking=False):
            self.send_json({"ok": False, "error": "A scan is already running. Try again in a few minutes."}, status=409)
            return
        try:
            completed = subprocess.run(
                command,
                cwd=script_path.parent,
                capture_output=True,
                text=True,
                timeout=420,
            )
        except subprocess.TimeoutExpired:
            SCAN_LOCK.release()
            self.send_json({"ok": False, "error": "Full scanner timed out after 7 minutes."}, status=504)
            return
        finally:
            if SCAN_LOCK.locked():
                try:
                    SCAN_LOCK.release()
                except RuntimeError:
                    pass

        if completed.returncode != 0:
            error_text = (completed.stderr or completed.stdout or "Scanner failed.").strip().splitlines()
            self.send_json({"ok": False, "error": error_text[-1] if error_text else "Scanner failed."}, status=500)
            return

        self.send_json({"ok": True, "report_url": f"/{output_name}?t={int(time.time())}"})

    def handle_test_alert(self) -> None:
        if not telegram_configured():
            self.send_json(
                {
                    "ok": False,
                    "error": "Telegram is not configured. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Render Environment.",
                },
                status=400,
            )
            return
        try:
            sent = send_test_alert()
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)
            return
        self.send_json({"ok": bool(sent)})

    def handle_test_trade_alerts(self) -> None:
        if not telegram_configured():
            self.send_json(
                {
                    "ok": False,
                    "error": "Telegram is not configured. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Render Environment.",
                },
                status=400,
            )
            return
        try:
            sent, messages = send_test_trade_alerts()
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)
            return
        self.send_json({"ok": sent == len(messages), "sent": sent, "messages": messages})

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, document: str, status: int = 200) -> None:
        body = document.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def serve_report(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parent
    os.chdir(root)
    server = http.server.ThreadingHTTPServer((args.host, args.port), ReportRequestHandler)
    start_scheduled_scanner()
    host = "127.0.0.1" if args.host in {"", "0.0.0.0"} else args.host
    print(f"Serving Stock Analyst App at http://{host}:{args.port}/app", flush=True)
    if os.environ.get("STOCK_ANALYST_PASSWORD"):
        print("Password protection is enabled. Username: stock", flush=True)
    print("Press Ctrl+C to stop the server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
    return 0


def default_server_port() -> int:
    try:
        return int(os.environ.get("PORT", "8765"))
    except ValueError:
        return 8765


def parse_server_port(value: str | int | None) -> int:
    if value is None:
        return default_server_port()
    text = str(value).strip()
    if text in {"$PORT", "${PORT}", ""}:
        return default_server_port()
    try:
        return int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid port: {text}") from exc


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank individual stocks using transparent market metrics.")
    parser.add_argument("symbols", nargs="*", help="Ticker symbols to analyze, for example AAPL MSFT NVDA")
    parser.add_argument("--serve", action="store_true", help="Start the private web app/dashboard server")
    parser.add_argument("--host", default="127.0.0.1", help="Host for --serve")
    parser.add_argument("--port", type=parse_server_port, default=default_server_port(), help="Port for --serve")
    parser.add_argument("--watchlist", choices=sorted(WATCHLISTS), help="Optional quick list; if omitted and no symbols are passed, screen --universe")
    parser.add_argument("--universe", choices=["liquid", "broad"], default="liquid", help="Use familiar liquid options names or the broad common-stock market")
    parser.add_argument("--mode", choices=["invest", "trade"], default="trade", help="Use trade for short-term catalyst-backed setups or invest for longer-term scoring")
    parser.add_argument("--strategy", choices=["patterns", "reversal", "breakout"], default="reversal", help="Use reversal for catalyst-backed dip rebounds/spike fades, patterns for strict chart-pattern scans, or breakout for continuation setups")
    parser.add_argument("--direction", choices=["both", "calls", "puts"], default="both", help="Trade direction to screen for")
    parser.add_argument("--profile", choices=["balanced", "growth", "income", "defensive"], default="balanced", help="Scoring profile")
    parser.add_argument("--limit", type=int, default=20, help="Number of rows to print in the terminal table")
    parser.add_argument("--keep", type=int, default=80, help="Number of top candidates to keep in the HTML report")
    parser.add_argument("--output", default="stock_report.html", help="HTML report path")
    parser.add_argument("--single", action="store_true", help="Analyze explicitly supplied ticker(s) even if they miss the normal scanner filters")
    parser.add_argument("--min-price", type=float, default=10.0, help="Exclude low-priced stocks below this price")
    parser.add_argument("--min-dollar-volume", type=float, default=25_000_000.0, help="Exclude thinly traded stocks below this 30-day average dollar volume")
    parser.add_argument("--min-1y-return", type=float, default=-0.05, help="Minimum 1-year return as a decimal, for example 0.10 means 10%%")
    parser.add_argument("--min-6m-return", type=float, default=-0.05, help="Minimum 6-month return as a decimal")
    parser.add_argument("--max-volatility", type=float, default=0.55, help="Maximum annualized volatility as a decimal")
    parser.add_argument("--max-drawdown", type=float, default=0.35, help="Maximum one-year drawdown as a positive decimal")
    parser.add_argument("--min-setup-score", type=float, default=50.0, help="In trade mode, require at least this short-term setup score")
    parser.add_argument("--profit-filters", dest="profit_filters", action="store_true", default=False, help="Use stricter backtest-informed filters for reversal trades")
    parser.add_argument("--no-profit-filters", dest="profit_filters", action="store_false", help="Use the original looser reversal trade filters")
    parser.add_argument("--min-call-setup-score", type=float, default=70.0, help="Optimized reversal mode: minimum setup score for CALL dip-rebound trades")
    parser.add_argument("--min-put-setup-score", type=float, default=80.0, help="Optimized reversal mode: minimum setup score for PUT fade trades")
    parser.add_argument("--require-put-catalyst", dest="require_put_catalyst", action="store_true", default=True, help="Optimized reversal mode: require strong catalyst confirmation for PUT trades")
    parser.add_argument("--allow-puts-without-catalyst", dest="require_put_catalyst", action="store_false", help="Optimized reversal mode: allow PUT trades without strong catalyst confirmation")
    parser.add_argument("--min-put-catalyst-score", type=float, default=78.0, help="Optimized reversal mode: minimum catalyst score for PUT trades")
    parser.add_argument("--min-volume-ratio", type=float, default=0.4, help="In trade mode, require current volume to be this multiple of 20-day average volume")
    parser.add_argument("--min-20d-return", type=float, default=0.0, help="In trade mode, require at least this 20-day return")
    parser.add_argument("--min-reversal-move", type=float, default=0.0, help="In reversal mode, require at least this 20-day dip for calls or spike for puts")
    parser.add_argument("--trade-require-uptrend", action="store_true", default=False, help="In trade mode, require price > 50-day average > 200-day average")
    parser.add_argument("--options", dest="options", action="store_true", default=True, help="Include suggested option contract details for top trade setups")
    parser.add_argument("--no-options", dest="options", action="store_false", help="Skip option contract lookup")
    parser.add_argument("--options-provider", choices=["nasdaq", "tradier", "yahoo", "none"], default="nasdaq", help="Options chain provider; nasdaq is free/no token but less stable")
    parser.add_argument("--min-dte", type=int, default=14, help="Minimum days to expiration for suggested option contracts")
    parser.add_argument("--max-dte", type=int, default=30, help="Maximum days to expiration for suggested option contracts")
    parser.add_argument("--require-uptrend", action="store_true", default=True, help="Require price > 50-day average > 200-day average")
    parser.add_argument("--allow-downtrends", dest="require_uptrend", action="store_false", help="Do not require moving-average uptrend")
    parser.add_argument("--exclude-overbought", action="store_true", default=True, help="Exclude stocks with RSI above 70")
    parser.add_argument("--allow-overbought", dest="exclude_overbought", action="store_false", help="Allow RSI above 70")
    parser.add_argument("--max-symbols", type=int, help="Limit the broad-market universe for faster test runs")
    parser.add_argument("--progress", type=int, default=100, help="Print progress every N symbols while broad screening")
    parser.add_argument("--fundamentals", dest="skip_quotes", action="store_false", help="Try Yahoo quote/fundamental lookup for P/E, dividends, beta, and market cap")
    parser.add_argument("--skip-quotes", dest="skip_quotes", action="store_true", default=True, help="Skip Yahoo quote/fundamental lookup; currently the default because Yahoo often blocks this endpoint")
    parser.add_argument("--verbose", action="store_true", help="Print every skipped symbol error")
    parser.add_argument("--notify", action="store_true", help="Send Telegram alerts for qualifying trade setups")
    parser.add_argument("--news", dest="news", action="store_true", default=True, help="Include recent Yahoo Finance headlines in the HTML report")
    parser.add_argument("--no-news", dest="news", action="store_false", help="Skip headline lookup")
    parser.add_argument("--catalysts", dest="catalysts", action="store_true", default=True, help="Use recent headlines, hype terms, and geopolitical/macro terms to adjust trade rankings")
    parser.add_argument("--no-catalysts", dest="catalysts", action="store_false", help="Do not adjust rankings using headline catalyst scoring")
    parser.add_argument("--require-catalyst-backing", dest="require_catalyst_backing", action="store_true", default=True, help="Require at least a C-grade fresh catalyst score for scanner results")
    parser.add_argument("--allow-weak-catalysts", dest="require_catalyst_backing", action="store_false", help="Allow scanner results even when the current catalyst score is weak")
    parser.add_argument("--min-catalyst-score", type=float, default=55.0, help="Minimum catalyst score when --require-catalyst-backing is active")
    parser.add_argument("--catalyst-weight", type=float, default=0.60, help="How much catalyst score affects final trade rank; 0.60 means 40%% chart and 60%% catalyst")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    raw_args = argv if argv is not None else sys.argv[1:]
    args = parse_args(raw_args)
    if not raw_args and os.environ.get("PORT"):
        args.serve = True
        args.host = "0.0.0.0"
    if args.serve:
        return serve_report(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
