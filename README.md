# PT-1 — JVT Studio Monitor

Watches [PropertyFinder](https://www.propertyfinder.ae/) for **studio apartments
for sale in Jumeirah Village Triangle (JVT) priced at or below AED 600,000** and
sends you a **Telegram** message the moment a new one is listed.

It runs automatically on **GitHub Actions** every 30 minutes — no computer of
your own needs to stay on. Each listing is only ever alerted once (already-seen
listings are tracked in `seen_listings.json`, committed back to the repo).

---

## How it works

1. `property_monitor/check.py` fetches the PropertyFinder search page for JVT
   studios, sorted newest-first.
2. It parses the listings embedded in the page (`__NEXT_DATA__` JSON), keeps the
   ones at/under AED 600,000, and compares them against `seen_listings.json`.
3. Any new listing is pushed to your Telegram, and the state file is updated.

PropertyFinder is protected by Cloudflare, so the fetcher uses `curl_cffi` to
mimic a real browser's TLS fingerprint. If Cloudflare ever blocks the GitHub
runner's IP, you can route traffic through a residential-proxy scraping API
(see [Optional: proxy fallback](#optional-proxy-fallback)).

---

## One-time setup

### 1. Create a Telegram bot

1. In Telegram, open a chat with **@BotFather**.
2. Send `/newbot`, follow the prompts, and copy the **bot token** it gives you
   (looks like `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxx`).
3. Open a chat with **your new bot** and send it any message (e.g. `hi`). This
   is required before the bot is allowed to message you.
4. Get your **chat ID**: open this URL in a browser (paste your token in):
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   Find `"chat":{"id":<NUMBER>...}` in the response — that number is your chat ID.

### 2. Add the secrets to GitHub

In this repo: **Settings → Secrets and variables → Actions → New repository
secret**, add:

| Secret name           | Value                          |
|-----------------------|--------------------------------|
| `TELEGRAM_BOT_TOKEN`  | the bot token from BotFather   |
| `TELEGRAM_CHAT_ID`    | your numeric chat ID           |

### 3. Done

The workflow (`.github/workflows/property-monitor.yml`) runs every 30 minutes.
To test it immediately, go to the **Actions** tab → **JVT Studio Monitor** →
**Run workflow**.

> On the very first run, every current in-budget listing is recorded as "seen"
> **without** alerting (so you aren't flooded). You'll get Telegram messages
> only for listings that appear *after* that.

---

## Configuration

All settings are environment variables, overridable in the workflow file:

| Variable             | Default                                   | Meaning                                  |
|----------------------|-------------------------------------------|------------------------------------------|
| `PF_MAX_PRICE`       | `600000`                                  | Max price in AED                         |
| `PF_SEARCH_URL`      | JVT studios-for-sale, newest-first        | The PropertyFinder search to monitor     |
| `PF_PAGES`           | `2`                                       | How many result pages to scan per run    |
| `PF_STATE_FILE`      | `seen_listings.json`                      | Where seen-listing IDs are stored        |

**Want a different area, price, or property type?** Build the search you want on
PropertyFinder in your browser, copy the resulting URL, and set it as the
`PF_SEARCH_URL` env in the workflow (append `?ob=nd` to sort newest-first).

---

## Optional: proxy fallback

GitHub Actions runners use datacenter IPs, which Cloudflare *may* block. If runs
start failing with HTTP 403, sign up for a free [ScraperAPI](https://www.scraperapi.com/)
key (1,000 requests/month free) and add one more secret:

| Secret name        | Value                |
|--------------------|----------------------|
| `SCRAPER_API_KEY`  | your ScraperAPI key  |

Then add `SCRAPER_API_KEY: ${{ secrets.SCRAPER_API_KEY }}` under the `env:` block
of the **Run monitor** step. Requests will be routed through residential IPs with
JS rendering. (To use a different provider, also set `SCRAPER_API_ENDPOINT` to a
template containing `{key}` and `{url}`.)

---

## Run locally

```bash
pip install -r property_monitor/requirements.txt
export TELEGRAM_BOT_TOKEN=...   # from BotFather
export TELEGRAM_CHAT_ID=...     # your chat ID
python property_monitor/check.py
```
