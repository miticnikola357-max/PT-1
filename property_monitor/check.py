#!/usr/bin/env python3
"""
PropertyFinder JVT studio monitor.

Fetches the PropertyFinder search page for studio apartments for sale in
Jumeirah Village Triangle (JVT), filters to listings at or below a max price,
and sends a Telegram message for any listing it has not seen before.

State (the set of listing IDs already notified) is stored in a JSON file so
that re-runs only alert on genuinely new listings. In GitHub Actions this file
is committed back to the repo to persist between scheduled runs.

Configuration is via environment variables (see README). Nothing secret is
hard-coded.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from curl_cffi import requests as cffi_requests

# --- Configuration ---------------------------------------------------------

# Default search: studio apartments for sale in Jumeirah Village Triangle,
# sorted newest-first (ob=nd) so the freshest listings are on page 1.
DEFAULT_SEARCH_URL = (
    "https://www.propertyfinder.ae/en/buy/dubai/"
    "studio-apartments-for-sale-jumeirah-village-triangle.html?ob=nd"
)

SEARCH_URL = os.environ.get("PF_SEARCH_URL", DEFAULT_SEARCH_URL)
MAX_PRICE = int(os.environ.get("PF_MAX_PRICE", "600000"))
PAGES_TO_SCAN = int(os.environ.get("PF_PAGES", "2"))
STATE_FILE = Path(os.environ.get("PF_STATE_FILE", "seen_listings.json"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# Where the auto-detected chat ID is cached so it only has to be discovered
# once (the workflow commits this back to the repo).
CHAT_ID_FILE = Path(os.environ.get("TELEGRAM_CHAT_ID_FILE", "telegram_chat_id.txt"))

# Optional: route page fetches through a scraping API with residential IPs +
# JS rendering. Set SCRAPER_API_KEY (and optionally SCRAPER_API_ENDPOINT) if
# Cloudflare starts blocking the runner's IP directly. Works out of the box
# with ScraperAPI's free tier; the endpoint template uses {key} and {url}.
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")
SCRAPER_API_ENDPOINT = os.environ.get(
    "SCRAPER_API_ENDPOINT",
    "https://api.scraperapi.com/?api_key={key}&url={url}",
)

SITE_ROOT = "https://www.propertyfinder.ae"

# Browser-like headers. PropertyFinder sits behind Cloudflare and rejects
# requests that do not look like a real browser, so we present a full set.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


# --- Fetching --------------------------------------------------------------

def _do_get(url: str) -> tuple[int, str]:
    """Single GET. Uses the scraping API if configured, otherwise curl_cffi
    with a real Chrome TLS fingerprint to get past Cloudflare's bot checks."""
    if SCRAPER_API_KEY:
        from urllib.parse import quote
        proxied = SCRAPER_API_ENDPOINT.format(
            key=SCRAPER_API_KEY, url=quote(url, safe="")
        )
        resp = cffi_requests.get(proxied, timeout=70)
        return resp.status_code, resp.text
    resp = cffi_requests.get(
        url, headers=HEADERS, impersonate="chrome", timeout=30
    )
    return resp.status_code, resp.text


def fetch_page(url: str) -> str:
    """GET a URL with retries, returning the HTML body."""
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            status, text = _do_get(url)
            if status == 200:
                return text
            last_err = RuntimeError(f"HTTP {status} for {url}")
        except Exception as exc:  # network / TLS error
            last_err = exc
        time.sleep(2 ** attempt)  # 1, 2, 4, 8s backoff
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


def paged_url(base: str, page: int) -> str:
    """Append the page query param to a search URL."""
    if page <= 1:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}page={page}"


# --- Parsing ---------------------------------------------------------------

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def extract_next_data(page_html: str) -> dict | None:
    """Pull the __NEXT_DATA__ JSON blob out of the page, if present."""
    match = NEXT_DATA_RE.search(page_html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _looks_like_listing(obj: dict) -> bool:
    """Heuristic: an object is a property listing if it has an id, a price,
    and something that looks like a link to the property page."""
    if not isinstance(obj, dict):
        return False
    has_id = any(k in obj for k in ("id", "listingId", "reference"))
    has_link = any(k in obj for k in ("share_url", "shareUrl", "details_path",
                                      "detailsPath", "url", "slug"))
    has_price = "price" in obj
    return has_id and has_link and has_price


def _price_value(price) -> int | None:
    """Normalise a price field (which may be a number, string, or dict) to an
    integer AED value."""
    if isinstance(price, (int, float)):
        return int(price)
    if isinstance(price, str):
        digits = re.sub(r"[^\d]", "", price)
        return int(digits) if digits else None
    if isinstance(price, dict):
        for key in ("value", "amount", "price", "min"):
            if key in price:
                return _price_value(price[key])
    return None


def _link_value(obj: dict) -> str | None:
    for key in ("share_url", "shareUrl", "details_path", "detailsPath",
                "url", "slug"):
        if key in obj and obj[key]:
            return str(obj[key])
    return None


def _title_value(obj: dict) -> str:
    for key in ("title", "name", "headline", "property_title"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return "Studio apartment"


def find_listings(data: dict) -> list[dict]:
    """Recursively walk the parsed JSON and collect anything that looks like a
    property listing. This is intentionally schema-tolerant so it keeps working
    if PropertyFinder reshapes their data."""
    found: list[dict] = []
    seen_ids: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            if _looks_like_listing(node):
                listing_id = str(
                    node.get("id")
                    or node.get("listingId")
                    or node.get("reference")
                )
                if listing_id and listing_id not in seen_ids:
                    seen_ids.add(listing_id)
                    price = _price_value(node.get("price"))
                    link = _link_value(node)
                    found.append(
                        {
                            "id": listing_id,
                            "title": _title_value(node),
                            "price": price,
                            "url": urljoin(SITE_ROOT, link) if link else SITE_ROOT,
                        }
                    )
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return found


# --- State -----------------------------------------------------------------

def load_seen() -> set[str]:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()


def save_seen(ids: set[str]) -> None:
    STATE_FILE.write_text(json.dumps(sorted(ids), indent=2))


# --- Notifying -------------------------------------------------------------

def resolve_chat_id() -> str:
    """Figure out which Telegram chat to message.

    Order of preference:
      1. The TELEGRAM_CHAT_ID env var, if set.
      2. A previously auto-detected ID cached in CHAT_ID_FILE.
      3. Auto-detect: ask Telegram for recent messages sent to the bot and use
         the most recent chat. This means the user only has to send their bot a
         message once -- no hunting for their numeric ID.
    The detected ID is cached so detection only happens on first setup.
    """
    if TELEGRAM_CHAT_ID:
        return TELEGRAM_CHAT_ID
    if CHAT_ID_FILE.exists():
        cached = CHAT_ID_FILE.read_text().strip()
        if cached:
            return cached
    if not TELEGRAM_BOT_TOKEN:
        return ""
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            timeout=30,
        )
        updates = resp.json().get("result", [])
        for update in reversed(updates):  # newest first
            message = update.get("message") or update.get("my_chat_member") or {}
            chat = message.get("chat", {})
            if chat.get("id") is not None:
                chat_id = str(chat["id"])
                CHAT_ID_FILE.write_text(chat_id)
                print(f"Auto-detected Telegram chat ID and cached it: {chat_id}")
                return chat_id
    except (requests.RequestException, ValueError) as exc:
        print(f"Could not auto-detect chat ID: {exc}", file=sys.stderr)
    print("WARNING: No Telegram chat ID yet. Send your bot a message in "
          "Telegram, then re-run.", file=sys.stderr)
    return ""


def send_telegram(listings: list[dict]) -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("WARNING: TELEGRAM_BOT_TOKEN not set; skipping notification.",
              file=sys.stderr)
        return
    chat_id = resolve_chat_id()
    if not chat_id:
        return
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for listing in listings:
        price = listing["price"]
        price_str = f"AED {price:,}" if price is not None else "Price on request"
        text = (
            f"🏠 <b>New JVT studio under AED {MAX_PRICE:,}</b>\n\n"
            f"{html.escape(listing['title'])}\n"
            f"💰 {price_str}\n"
            f'🔗 <a href="{html.escape(listing["url"])}">View listing</a>'
        )
        resp = requests.post(
            api,
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "false",
            },
            timeout=30,
        )
        if not resp.ok:
            print(f"Telegram send failed: {resp.status_code} {resp.text}",
                  file=sys.stderr)


# --- Main ------------------------------------------------------------------

def main() -> int:
    all_listings: dict[str, dict] = {}

    for page in range(1, PAGES_TO_SCAN + 1):
        url = paged_url(SEARCH_URL, page)
        print(f"Fetching page {page}: {url}")
        try:
            page_html = fetch_page(url)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            # If the very first page fails, treat it as a hard failure so the
            # workflow surfaces it; later pages failing is non-fatal.
            if page == 1:
                return 1
            break

        data = extract_next_data(page_html)
        if data is None:
            print("WARNING: could not find __NEXT_DATA__ on page; "
                  "the page layout may have changed.", file=sys.stderr)
            if page == 1:
                return 1
            break

        for listing in find_listings(data):
            all_listings[listing["id"]] = listing

        time.sleep(1)  # be polite between page requests

    print(f"Parsed {len(all_listings)} listing(s) total.")

    # Filter to studios within budget.
    within_budget = [
        lst for lst in all_listings.values()
        if lst["price"] is not None and lst["price"] <= MAX_PRICE
    ]
    print(f"{len(within_budget)} listing(s) at or below AED {MAX_PRICE:,}.")

    seen = load_seen()
    new_listings = [lst for lst in within_budget if lst["id"] not in seen]
    print(f"{len(new_listings)} new listing(s) to notify.")

    if new_listings:
        send_telegram(new_listings)
        for lst in new_listings:
            seen.add(lst["id"])

    # Record every in-budget listing we saw so we never re-alert, even if the
    # notification for some reason did not fire this run.
    for lst in within_budget:
        seen.add(lst["id"])
    save_seen(seen)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
