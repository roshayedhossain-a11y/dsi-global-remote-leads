# DSI Ultimate Global Remote Lead Engine v4

## One-line decision

Use v4. It is the strongest version.

## Version comparison

| Version | What it was | Keep or replace |
|---|---|---|
| v1 | Basic Python engine with core public sources | Replace |
| v2 | Added the uploaded 500+ source catalog and company watchlist | Replace |
| v3 | Added stronger Tier 1 sources, ATS discovery, and hard filtering | Replace |
| v4 | v3 plus Review Queue, cleaner free workflow controls, stronger beginner docs, and stricter daily operating model | Use this |

## What makes v4 stronger

1. It keeps the strict `Global Leads` tab clean for outreach.
2. It also writes `Review Queue` rows for jobs that are remote but not proven global.
3. It keeps country-locked roles out of outreach.
4. It uses APIs and feeds first, then HTML pages, then company ATS discovery.
5. It rotates big company/source lists so the free GitHub runner does not burn out.
6. It logs every source into `Source Health` so you know exactly what worked and what failed.

## The machine has three data lanes

### Lane 1: Outreach ready

Rows go to `Global Leads` only if they pass strict filters:

- GLOBAL_OK
- BANGLADESH_OK

These are the only rows you should contact directly.

### Lane 2: Research queue

Rows go to `Review Queue` if they are technical roles but the job post does not prove global hiring.

Use this tab for manual checking. Do not outreach before checking.

### Lane 3: Rejected silently

Rows are rejected if they are:

- Not technical
- Country restricted
- Hybrid or onsite
- Citizenship or work authorization locked
- Duplicates
- Broken links when link validation is enabled

## Daily operating rule

Every morning, check these tabs in order:

1. `Run Stats`
2. `Source Health`
3. `Global Leads`
4. `Review Queue`

Do not obsess over raw source count. The only number that matters is clean ICP companies you can contact.

## Free setup limits

This is still a free engine. It is strong, but not magic.

Realistic output:

- 100 to 300 raw jobs per run
- 30 to 100 strict qualified global roles on good days
- 20 to 60 strong companies after human review

Some days will be lower. That is normal.

## Strict definition of DSI ICP

A company is useful for DSI only when it has active technical hiring and the job post proves one of these:

- Worldwide
- Anywhere in the world
- Work from anywhere
- Global remote
- Open to international candidates
- No location requirement
- Distributed team
- Contractor worldwide
- Bangladesh accepted

A company is not useful if the post says:

- US only
- UK only
- EU only
- Europe only
- Canada only
- Australia only
- Must be authorized to work in a specific country
- Must live in a specific country
- Hybrid
- Onsite
- Relocation required
- Security clearance
- Citizenship required

## Best free path

Use this exact stack:

- Python for scraping
- GitHub Actions for daily running
- Google Sheets for output
- Supabase only when you want database history

Do not go back to Google Apps Script as the scraper. Sheets is the dashboard, not the engine.
