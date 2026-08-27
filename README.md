# Federal Document Tracker

Scheduled scrapers for the sources on the regulatory/financial + national
security/DOJ/courts + Congress/oversight dashboard, publishing results as
RSS feeds you can subscribe to in any feed reader.

Runs on **GitHub Actions** hourly by default, stores versioned events
in **Neon Postgres**, and publishes feeds via **GitHub Pages**.

Each event also has queryable columns for its event date, company, broader
entity, department/agency, amount, currency, and amount type. Values supplied
by an API (for example a USASpending award total) are labelled separately from
dollar figures inferred from release text (`mentioned_amount`).

The live archive retains seven UTC calendar dates: today and the preceding six
days. Older and future-dated source records are rejected; undated records expire
seven calendar dates after first discovery. The hourly run also physically
prunes anything outside that window before rebuilding the feeds.

## What's covered

| Category | Sources |
|---|---|
| SEC | New filings (8-K, SC 13D/A, NT filings) via EDGAR daily index; litigation releases; administrative proceedings |
| FEC | Recent filings via OpenFEC |
| Lobbying | LD-2/LD-203 filings via LDA.gov |
| Courts / DOJ | New RECAP docket activity (CourtListener); DOJ press releases |
| Congress / oversight | Recent bill activity (Congress.gov); Federal Register documents |
| Adjacent | USASpending awards; CFPB complaints; OFAC sanctions actions* |

\* No official API — HTML-scraped, and the most likely to break if the
source site redesigns. See "Fragile scrapers" below.

## One important design note

**SEC's `robots.txt` disallows `/cgi-bin`**, which rules out the "current
filings" atom feed for automated use. This project instead pulls SEC's
**daily index files** (`/Archives/edgar/daily-index/`), which are the
SEC-sanctioned machine-readable path and are explicitly allowed. If you
ever add your own SEC scraper, check `https://www.sec.gov/robots.txt`
first and stay off `/cgi-bin`.

## Setup

### 1. Create the repo
Push this folder to a new GitHub repository (public — GitHub Pages on the
free tier requires a public repo, or a paid plan for private Pages).

```bash
cd gov-doc-tracker
git add -A
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

### 2. Add secrets (Settings → Secrets and variables → Actions)

None are strictly required to get *something* running — every scraper
fails gracefully into "0 items" if its key is missing — but you'll get
much better coverage with these free keys:

| Secret | Where to get it | Required? |
|---|---|---|
| `SCRAPER_CONTACT_EMAIL` | Your own email | Recommended — SEC and other sites ask for a contact-identifying User-Agent |
| `FEC_API_KEY` | https://api.data.gov/signup/ | Optional (falls back to shared `DEMO_KEY`, very low limit) |
| `LDA_API_KEY` | https://lda.gov/api/register/ | Optional (anonymous access works, harder rate limit) |
| `COURTLISTENER_TOKEN` | https://www.courtlistener.com/ (free account) | Optional |
| `CONGRESS_API_KEY` | https://api.congress.gov/sign-up/ | **Required** for the Congress.gov scraper — it returns nothing without a key |
| `DATABASE_URL` | Written by `neon env pull` | **Required** — pooled Neon connection used by the application |
| `DATABASE_URL_UNPOOLED` | Written by `neon env pull` | **Required** — direct Neon connection used for migrations |

### 3. Enable GitHub Pages
Settings → Pages → Source: "Deploy from a branch" → Branch: `main`,
folder: `/docs`. Save.

Your feeds will be live at:
```
https://<your-username>.github.io/<your-repo>/feeds/all.xml
https://<your-username>.github.io/<your-repo>/feeds/sec.xml
https://<your-username>.github.io/<your-repo>/feeds/fec.xml
https://<your-username>.github.io/<your-repo>/feeds/lobbying.xml
https://<your-username>.github.io/<your-repo>/feeds/courts.xml
https://<your-username>.github.io/<your-repo>/feeds/congress.xml
https://<your-username>.github.io/<your-repo>/feeds/adjacent.xml
```
An index page listing all of them is at the repo's Pages root.

### 4. Trigger the first run manually
Actions tab → "Scrape federal document sources" → "Run workflow." Don't
wait for the schedule the first time — you want to see it succeed (or
fail loudly) before trusting the cron.

### 5. Subscribe
Paste any feed URL into Feedly, Inoreader, NetNewsWire, or your reader of
choice.

## Adjusting what's tracked

- **SEC form types**: edit `FORM_TYPES` in `scrapers/sec_edgar.py`.
- **Court tracking**: `scrapers/courts.py` pulls the general RECAP
  firehose by default. Set a `COURTLISTENER_QUERY` secret (a company or
  person name) to narrow it to filings mentioning that name instead.
- **Schedule frequency**: edit the `cron` line in
  `.github/workflows/scrape.yml`. The default is hourly; SEC in particular
  asks scripted clients to keep request rates modest, so avoid needlessly
  aggressive polling.

## Fragile scrapers (no official API)

`scrapers/ofac.py` parses HTML because OFAC doesn't offer a public API. If
it starts returning 0 items consistently (check the Actions run logs),
the site's markup likely changed — view-source the page and update the
CSS selectors near the top of the file.

**Removed:** GAO and Oversight.gov scrapers were dropped. GAO's site
appears to actively block automated requests (403 + robots.txt disallow
on its own RSS documentation page). Oversight.gov's URL and markup
proved unreliable to keep synced remotely. Both can be revisited later —
GAO's WAF may need a different approach entirely (e.g. routing through
GovInfo's GAO Reports collection instead of gao.gov directly), and
Oversight.gov just needs someone testing against the live page directly.

## Local testing

```bash
pip install -r requirements.txt
neon env pull
python migrate.py
python backfill_structured.py
python build_feeds.py
```

`neon env pull` writes the linked branch's pooled and direct connection
strings to the gitignored `.env.local`. Feeds land in `docs/feeds/`; durable
event versions remain in Neon even when a source is temporarily unavailable.

## Local reporting dashboard

Run the **dashboard** process from Conductor, or start it manually:

```bash
.venv/bin/python dashboard.py --port 8000
```

Then open `http://127.0.0.1:8000`. It reads the linked Neon database through a
localhost-only Python process and refreshes every 30 seconds. You can search and
filter by company, department, source, amount range, and date range, and sort by
amount to surface unusually large payments. Database credentials remain in the
server-side `.env.local`; they are never sent to the browser.

The generated RSS files expose the same structured values as namespaced
`gov:company`, `gov:entity`, `gov:department`, `gov:amount`, `gov:amountType`,
and `gov:eventDate` elements. Common feed readers can also filter companies and
departments through ordinary RSS categories.
