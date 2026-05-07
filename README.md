# DSI Global Remote Lead Engine

This is a free beginner-friendly lead engine for DSI Innovators.

It finds active remote engineering hiring signals, filters out country-restricted jobs, deduplicates rows, and writes the final qualified leads into Google Sheets.

## What this engine does

1. Scrapes free public job sources.
2. Scrapes ATS job boards from Greenhouse, Lever, Ashby, Workable HTML pages, and SmartRecruiters where public links are found.
3. Keeps only tech roles.
4. Keeps only jobs that show global remote or Bangladesh-friendly hiring evidence.
5. Rejects country-locked remote jobs.
6. Deduplicates by job URL.
7. Writes output to CSV.
8. Writes output to Google Sheets if you set Google secrets.
9. Writes history to Supabase if you set Supabase secrets.
10. Logs every source in Source Health.

## What this engine does not do

It does not create unlimited data.
No free tool can do that.
It creates a daily pipeline of stronger, cleaner, more usable data.

It also does not scrape Google search results directly. Your uploaded 500+ source file contains many Google SERP queries. The engine saves those as a research queue, but it does not run them unless you later add a real search API. Free Google scraping is unstable and gets blocked. Instead, this engine uses the company domains from that file and tries to discover public ATS pages directly from the company career pages.

## Beginner setup

### Step 1: Create GitHub account

Go to GitHub and create an account.

### Step 2: Create a new public repository

Name it:

```text
dsi-global-remote-leads
```

Make it public if you want free GitHub Actions usage.

### Step 3: Upload these files

Upload every file from this folder to your GitHub repository.

### Step 4: Prepare your Google Sheet

Use your existing Google Sheet.
Copy the Sheet ID from the URL.

Example:

```text
https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
```

### Step 5: Create Google service account

1. Go to Google Cloud Console.
2. Create a project.
3. Enable Google Sheets API.
4. Enable Google Drive API.
5. Create a service account.
6. Create a JSON key.
7. Copy the full JSON.
8. Share your Google Sheet with the service account email.

The service account email looks like this:

```text
something@project-id.iam.gserviceaccount.com
```

Give it Editor access to your Google Sheet.

### Step 6: Add GitHub secrets

Go to your GitHub repo.

Settings > Secrets and variables > Actions > New repository secret

Add these:

```text
GOOGLE_SHEET_ID
GOOGLE_SERVICE_ACCOUNT_JSON
```

Optional Supabase secrets:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

### Step 7: Run manually first

Go to:

Actions > DSI Global Remote Lead Engine > Run workflow

Wait for it to finish.

### Step 8: Check your Google Sheet

You should see these tabs:

1. Global Leads
2. Source Health
3. Run Stats


## New in v2: your 500+ source catalog is included

I added your uploaded source list into:

```text
config/source_catalog.csv
config/expanded_sources.json
config/serp_queries_research_queue.csv
```

The engine now uses the catalog in 3 practical ways:

1. Extra RSS feeds and RSS hub pages.
2. Public HTML job/category pages from strong remote job boards.
3. A company watchlist of remote-friendly companies. The engine visits company career pages and tries to discover Greenhouse, Lever, Ashby, Workable, and SmartRecruiters links.

The Google SERP queries are kept as a research queue. They are useful later if you add a search API, but they are not scraped for free because that will break often.

## Free runner control settings

These are inside `.github/workflows/daily-leads.yml`:

```yaml
MAX_PER_SOURCE: "150"
MAX_HTML_SOURCES_PER_RUN: "35"
MAX_COMPANIES_PER_RUN: "80"
MAX_HTML_LINKS_PER_SOURCE: "80"
VALIDATE_JOB_LINKS: "false"
RUN_MODE: "strict"
```

Simple meaning:

1. `MAX_HTML_SOURCES_PER_RUN` controls how many public job board/category pages are checked each run.
2. `MAX_COMPANIES_PER_RUN` controls how many company career sites are checked each run.
3. The company list rotates daily, so the engine covers the full catalog over multiple days.
4. `VALIDATE_JOB_LINKS` can be changed to `true` later, but keep it false first because link validation adds many extra requests.
5. `RUN_MODE` should stay `strict` for outreach-ready rows. Use `review` only when researching.

## Strict mode vs review mode

Strict mode keeps only:

1. GLOBAL_OK
2. BANGLADESH_OK

Review mode also keeps jobs that need manual verification.

To change mode, edit this line in `.github/workflows/daily-leads.yml`:

```yaml
RUN_MODE: "strict"
```

Change it to:

```yaml
RUN_MODE: "review"
```

Use strict mode for outreach.
Use review mode for research.

## How to add more companies

Open:

```text
config/ats_companies.json
```

For the big source catalog, open:

```text
config/expanded_sources.json
```

Add company board names under:

1. greenhouse_boards
2. lever_companies
3. ashby_boards

Example:

```json
"greenhouse_boards": ["gitlab", "automattic", "zapier"]
```

Only add companies that use that ATS.
Wrong board names will fail safely and appear in Source Health.

## How to add more RSS feeds

Open:

```text
config/sources.json
```

Add a new item under `generic_rss`:

```json
{
  "name": "Example RSS",
  "url": "https://example.com/jobs/feed"
}
```

## Supabase setup

Run the SQL in:

```text
sql/supabase_schema.sql
```

Then add your Supabase secrets in GitHub.

Supabase is optional.
Use it when your lead history gets bigger.

## Important rule

Remote is not enough.
Only contact companies when the row says:

1. GLOBAL_OK
2. BANGLADESH_OK

If it says NEEDS_VERIFICATION, verify manually first.

If it says COUNTRY_RESTRICTED, do not contact.

## Daily target

Realistic free target:

1. 100 to 300 raw jobs per run
2. 30 to 100 qualified rows after strict filtering
3. 20 to 60 strong outreach targets after manual review

This is enough to start booking meetings if your messaging is sharp.


## v3 Strength Upgrade

This version adds stronger daily sources from the uploaded catalog and from the final source plan:

- Himalayas official worldwide API search for 17 engineering keyword groups.
- JobsCollider public search API for software development, DevOps, data, QA, and cybersecurity.
- Real Work From Anywhere direct RSS feeds for all jobs plus fullstack, frontend, backend, software development, and DevOps.
- WorkAnywhere.pro direct RSS feeds for all jobs plus developer, engineer, frontend, backend, fullstack, and data/AI.
- Always-on high-signal HTML sources: We Work Remotely anywhere/software pages, WeAreDistributed, Remote Rocketship, NoDesk, Working Nomads, Remote.co, JustRemote, Pangian, Remote First Jobs, Arc, and YC remote startup jobs.

Important: strict mode still accepts only GLOBAL_OK and BANGLADESH_OK. Remote-only, unknown-location, or country-specific jobs go to rejection/review.


## v4 Ultimate Upgrade

Use v4 as the final version. It includes everything from v3 and adds a second safety lane called `Review Queue`.

Simple rule:

1. `Global Leads` = outreach-ready.
2. `Review Queue` = check manually first.
3. `Source Health` = debug the machine.
4. `Run Stats` = measure the daily result.

New v4 workflow settings:

```yaml
MAX_REVIEW_ROWS: "500"
WRITE_REVIEW_QUEUE: "true"
```

Why this matters: strict filtering keeps your outreach clean, but the review queue stops you from losing possible good leads that need human checking. This is the correct balance between quality and volume.

Read `ULTIMATE_ENGINE_GUIDE.md` before running the engine.
