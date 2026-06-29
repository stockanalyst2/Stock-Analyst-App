#!/usr/bin/env python3
"""Download company logos into static/logos for the Atlas app.

The app itself serves logos locally from static/logos/TICKER.png. This helper
populates that folder from company domains so the production UI stays fast and
consistent after the files are committed.
"""

from __future__ import annotations

import argparse
import imghdr
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import stock_analyst


LOGO_DIR = Path(__file__).resolve().parent / "static" / "logos"

TICKER_DOMAINS = {
    "AAPL": "apple.com",
    "ABNB": "airbnb.com",
    "ADBE": "adobe.com",
    "AMD": "amd.com",
    "AMZN": "amazon.com",
    "ASTS": "ast-science.com",
    "AVGO": "broadcom.com",
    "BAC": "bankofamerica.com",
    "CL": "colgatepalmolive.com",
    "COST": "costco.com",
    "CRWD": "crowdstrike.com",
    "CVX": "chevron.com",
    "GIS": "generalmills.com",
    "GOOGL": "abc.xyz",
    "IONQ": "ionq.com",
    "JNJ": "jnj.com",
    "JPM": "jpmorganchase.com",
    "KMB": "kimberly-clark.com",
    "KO": "coca-colacompany.com",
    "KR": "thekrogerco.com",
    "LLY": "lilly.com",
    "MA": "mastercard.com",
    "MCD": "mcdonalds.com",
    "META": "meta.com",
    "MO": "altria.com",
    "MRK": "merck.com",
    "MSFT": "microsoft.com",
    "NFLX": "netflix.com",
    "NKE": "nike.com",
    "NOW": "servicenow.com",
    "NVDA": "nvidia.com",
    "O": "realtyincome.com",
    "ORCL": "oracle.com",
    "PANW": "paloaltonetworks.com",
    "PEP": "pepsico.com",
    "PG": "pg.com",
    "PM": "pmi.com",
    "RDW": "redwirespace.com",
    "RIVN": "rivian.com",
    "SHOP": "shopify.com",
    "SNOW": "snowflake.com",
    "T": "att.com",
    "TSLA": "tesla.com",
    "UNH": "unitedhealthgroup.com",
    "V": "visa.com",
    "VZ": "verizon.com",
    "WMT": "walmart.com",
    "XOM": "exxonmobil.com",
}

SIMPLE_ICON_SLUGS = {
    "AAPL": "apple",
    "ABNB": "airbnb",
    "ADBE": "adobe",
    "AMD": "amd",
    "AMZN": "amazon",
    "AVGO": "broadcom",
    "BAC": "bankofamerica",
    "CRWD": "crowdstrike",
    "CVX": "chevron",
    "GOOGL": "google",
    "IONQ": "ionq",
    "JPM": "jpmorgan",
    "MA": "mastercard",
    "META": "meta",
    "MSFT": "microsoft",
    "NFLX": "netflix",
    "NKE": "nike",
    "NOW": "servicenow",
    "NVDA": "nvidia",
    "ORCL": "oracle",
    "PANW": "paloaltonetworks",
    "PEP": "pepsi",
    "PG": "procterandgamble",
    "SHOP": "shopify",
    "SNOW": "snowflake",
    "TSLA": "tesla",
    "V": "visa",
    "VZ": "verizon",
    "WMT": "walmart",
}


def logo_urls(domain: str, simple_icon_slug: str = "") -> list[str]:
    encoded = urllib.parse.quote(domain.strip().lower())
    urls = [
        f"https://logo.clearbit.com/{encoded}?size=256",
        f"https://www.google.com/s2/favicons?domain={encoded}&sz=256",
    ]
    if simple_icon_slug:
        urls.append(f"https://cdn.simpleicons.org/{urllib.parse.quote(simple_icon_slug)}/FFFFFF")
    return urls


def request_bytes(url: str, timeout: int = 12) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AtlasLogoDownloader/1.0",
            "Accept": "image/png,image/*;q=0.9,*/*;q=0.5",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        data = response.read()
    if not content_type.startswith("image/"):
        raise ValueError(f"not an image response: {content_type or 'unknown content type'}")
    if len(data) < 256:
        raise ValueError("image response was too small to be a usable logo")
    return data


def image_extension(data: bytes) -> str:
    kind = imghdr.what(None, data)
    if kind == "jpeg":
        return ".jpg"
    if kind == "png":
        return ".png"
    if kind == "gif":
        return ".gif"
    if data.startswith(b"<svg"):
        return ".svg"
    return ".png"


def parse_domain_override(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Domain overrides must look like TICKER=domain.com")
    symbol, domain = value.split("=", 1)
    symbol = symbol.strip().upper()
    domain = domain.strip().lower()
    if not symbol or not domain:
        raise argparse.ArgumentTypeError("Domain overrides must include both ticker and domain")
    return symbol, domain


def symbols_from_args(args: argparse.Namespace) -> list[str]:
    symbols: list[str] = []
    if args.all_watchlists:
        for names in stock_analyst.WATCHLISTS.values():
            symbols.extend(names)
    for watchlist in args.watchlist or []:
        symbols.extend(stock_analyst.WATCHLISTS[watchlist])
    symbols.extend(args.symbols or [])
    if not symbols:
        symbols = ["ABNB", "PANW", "BAC"]
    return sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()})


def save_logo(symbol: str, data: bytes) -> Path:
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    extension = image_extension(data)
    path = LOGO_DIR / f"{symbol}.png"
    if extension != ".png":
        path = LOGO_DIR / f"{symbol}{extension}"
    path.write_bytes(data)
    return path


def download_logo(symbol: str, domain: str, force: bool = False) -> tuple[bool, str]:
    existing = LOGO_DIR / f"{symbol}.png"
    if existing.exists() and not force:
        return True, f"kept existing {existing}"
    last_error = ""
    for url in logo_urls(domain, SIMPLE_ICON_SLUGS.get(symbol, "")):
        try:
            path = save_logo(symbol, request_bytes(url))
            return True, f"saved {path}"
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            last_error = str(exc)
    return False, last_error or "no logo source returned an image"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download local Atlas watchlist logos into static/logos.")
    parser.add_argument("symbols", nargs="*", help="Ticker symbols to download, for example NVDA AAPL ABNB.")
    parser.add_argument(
        "--watchlist",
        action="append",
        choices=sorted(stock_analyst.WATCHLISTS),
        help="Download logos for one configured Atlas watchlist. Repeatable.",
    )
    parser.add_argument("--all-watchlists", action="store_true", help="Download logos for every configured Atlas watchlist.")
    parser.add_argument(
        "--domain",
        action="append",
        type=parse_domain_override,
        default=[],
        metavar="TICKER=DOMAIN",
        help="Override or add a ticker domain, for example BRK.B=berkshirehathaway.com.",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing local logo files.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to wait between downloads.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    domains = dict(TICKER_DOMAINS)
    domains.update(dict(args.domain))
    symbols = symbols_from_args(args)
    failures: list[str] = []
    for symbol in symbols:
        domain = domains.get(symbol)
        if not domain:
            failures.append(f"{symbol}: missing domain mapping; rerun with --domain {symbol}=company.com")
            continue
        ok, message = download_logo(symbol, domain, force=args.force)
        status = "OK" if ok else "FAIL"
        print(f"{status} {symbol}: {message}")
        if not ok:
            failures.append(f"{symbol}: {message}")
        time.sleep(max(0.0, args.sleep))
    if failures:
        print("\nSome logos were not downloaded:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
