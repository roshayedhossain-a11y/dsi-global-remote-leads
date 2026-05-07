# DSI Source Strategy

The uploaded 500+ source catalog is powerful, but not every row should be executed the same way.

## Executed automatically

The engine executes these free source types:

1. Public APIs already coded into the engine: Remotive, RemoteOK, Jobicy, Arbeitnow, Greenhouse, Lever, Ashby.
2. RSS and Atom feeds.
3. RSS hub pages where the engine can discover real feed URLs.
4. Public HTML job/category pages.
5. Company career pages from the company watchlist, then ATS discovery.

## Stored but not automatically executed

The source catalog contains many Google SERP queries. They are stored in:

```text
config/serp_queries_research_queue.csv
```

The free engine does not scrape Google result pages directly because it is unstable and will break. If you later add a proper search API, these queries become very valuable.

## Strong lead logic

The engine rejects country-locked remote roles before accepting anything.

Accept:

1. GLOBAL_OK
2. BANGLADESH_OK

Reject:

1. COUNTRY_RESTRICTED
2. NOT_TECH

Review manually:

1. NEEDS_VERIFICATION

## How to scale without paying

Increase these values slowly in `.github/workflows/daily-leads.yml`:

```yaml
MAX_HTML_SOURCES_PER_RUN: "35"
MAX_COMPANIES_PER_RUN: "80"
```

Do not max everything on day one. First make sure your Google Sheet receives clean data.
