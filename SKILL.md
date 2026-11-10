---
name: speaker
description: "B2B people, company, and web intelligence through the Speaker CLI. Use for people lookup, company research, competitive analysis, hiring/funding/news signals, and market exploration across the graph."
---

# Speaker

Root access for agents to the professional graph.

```
                         PROFESSIONAL GRAPH
                    source-of-truth nuclei + flat sidecars

┌──────────────────────────────────────────────────────────────────────┐
│ PEOPLE NUCLEUS                                                       │
│ people.nucleus = source of truth for professional people             │
│ key: person_id                                                       │
│ sidecars: people.contacts | people.roles_history | people.education  │
│           people.repos                                               │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ current_company_id
                           │ roles_history.speaker_company_id
                           ▼ entity_id
┌──────────────────────────────────────────────────────────────────────┐
│ COMPANIES NUCLEUS                                                    │
│ companies.nucleus = source of truth for professional companies       │
│ key: entity_id                                                       │
│ sidecars: identifiers | metrics | industry_keywords | jobs | posts   │
│           competitors | funding_rounds | web_outlinks                │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ website / domain / outlink domains
                           ▼ domain
┌──────────────────────────────────────────────────────────────────────┐
│ WEB GRAPH                                                            │
│ web.domain_entity_bridge = domain → entity_id resolver               │
│ web.pages = page evidence by domain                                  │
│ key: domain                                                          │
└──────────────────────────────────────────────────────────────────────┘
```

The insight is never in one table. It is in the hops from nuclei to sidecars to edges.

## Start here

```bash
speaker help
speaker mesh
speaker schema
speaker schema people.nucleus
speaker schema companies.nucleus
```

If curated local schema docs are missing or stale, use raw metadata:

```bash
speaker query "DESCRIBE people.nucleus"
speaker query "DESCRIBE companies.nucleus"
```

## Core rule

**Hops, not broad joins.**

Query one table, carry the right key forward, then hop to the next table.

The graph keys are:

- `person_id` — canonical Speaker person id.
- `entity_id` — canonical Speaker company/entity id.
- `domain` — normalized web/company fallback key.

Important: **graph-valid does not always mean physically fast**. Read each table schema's ClickHouse access notes. Fast queries usually match the table's `ORDER BY` left prefix.

## Main tables

People:

```text
people.nucleus          current person snapshot
people.contacts         contact/social handles
people.roles_history    career history
people.education        education history
people.repos            GitHub repositories with optional person link
```

Companies:

```text
companies.nucleus              company profile snapshot
companies.identifiers          websites/social/profile identifiers
companies.metrics              numeric/growth/traffic/review/funding metrics
companies.industry_keywords    rich taxonomy/facet signals
companies.jobs                 job postings
companies.posts                news/article mentions, not social posts
companies.competitors          competitor-domain edges
companies.funding_rounds       funding rounds
companies.web_outlinks         page-level external outlinks from company sites
```

Web:

```text
web.domain_entity_bridge   domain → entity_id resolver
web.pages                  crawled pages; enter by domain
```

## Query loop

SCOPE → SCHEMA → KEY → QUERY → CARRY → HOP

1. Scope the task.
2. Read `speaker schema` and the relevant table schema.
3. Identify the graph key: `person_id`, `entity_id`, or `domain`.
4. Query one table with a selective filter.
5. Carry IDs/domains forward.
6. Query the next table.
7. Repeat.

### Stay in the loop

Do not write a script — Python, a bash loop, or similar — that fires a batch of queries up front.

Stay in the loop: run one query, read the result, decide the next query from what you learned. Use code only to process results you already have, such as deduping, ranking, or formatting a large NDJSON dump saved to a file. Never use code to plan or fire the queries.

A static script decides the hops before it sees the data, so it misses the signal this loop is meant to find.

If a query-and-schema MCP tool is available, prefer it for this loop. Keep the CLI for when you need code to process results.

### After each result

Ask:

- What did I learn?
- Which key do I carry: `person_id`, `entity_id`, or `domain`?
- What is the next hop — which table, and why?
- Am I done?

Then run that next query. Do not batch the rest.

## Worked example

Buyer search for attio.com. The SQL runs against the live graph; results are described in words, not shown as rows.

Goal: learn what Attio is, then find likely buyer companies from graph evidence, one hop at a time.

**1. Resolve the starting domain.**

```bash
speaker query "SELECT domain, entity_id, resolution_status FROM web.domain_entity_bridge WHERE domain = 'attio.com'"
```

What this tells you: whether the domain resolves uniquely to a company, and if so, the `entity_id` to carry. If the domain is ambiguous or unresolved, `entity_id` is blank — keep hopping by `domain`.

**2. Read the company nucleus, using the `entity_id` from step 1.**

```bash
speaker query "SELECT entity_id, name, website, summary, keywords, offerings, market, customer_types, business_model, headcount, country FROM companies.nucleus WHERE entity_id = 'spkco_...'"
```

What this tells you: what the company does and who it sells to. Fields such as `customer_types`, `market`, and `offerings` define what a buyer looks like. The next hop depends on this profile, not on a prewritten list of tables.

**3. Enrich taxonomy for the same `entity_id`.**

```bash
speaker query "SELECT entity_id, li_industry, li_industries, li_specialities, crunchbase_categories FROM companies.industry_keywords WHERE entity_id = 'spkco_...'"
```

What this tells you: industry and speciality labels you can use later to judge candidate companies.

**4. Follow outlinks from Attio's own site.**

```bash
speaker query "SELECT source_entity_id, source_page_url, source_page_type, target_domain, target_entity_id, target_resolution_status FROM companies.web_outlinks WHERE source_entity_id = 'spkco_...' LIMIT 100"
```

What this tells you: domains Attio already links to, and `target_entity_id` when those domains resolve. Some `source_page_url` values will look like customer or case-study pages; those targets are the first buyer candidates. Carry the interesting `target_domain` and `target_entity_id` values.

**5. Inspect page evidence on attio.com. Do not select `text` yet.**

```bash
speaker query "SELECT url, title, desc, page_type FROM web.pages WHERE domain = 'attio.com' LIMIT 50"
```

What this tells you: which pages exist — product, pricing, customers, case studies. Use titles and URLs to decide the next hop, such as resolving a domain you just learned or revisiting outlinks from a specific page.

**6. Resolve only domains you actually saw.**

```bash
speaker query "SELECT domain, entity_id, resolution_status FROM web.domain_entity_bridge WHERE domain IN ('...')"
```

Put domains from the outlink or page results in the `IN` list. Do not guess them in advance. Do not match candidates by company name: names are ambiguous, domains are not.

**7. Profile those candidate companies.**

```bash
speaker query "SELECT entity_id, name, website, summary, keywords, offerings, market, customer_types, headcount, country FROM companies.nucleus WHERE entity_id IN ('spkco_...', 'spkco_...')"
```

What this tells you: whether each candidate looks like a buyer given Attio's profile. Drop or keep them before hopping further.

If you still need signal, hop the same `entity_id`s into `companies.metrics` or `companies.jobs`. `companies.competitors`, `companies.posts`, and `companies.funding_rounds` are later hops only if the last result says you need them — not a default batch.

Finding people at those companies by `people.nucleus.current_company_id` or `people.roles_history.speaker_company_id` is graph-valid but not ORDER BY-prefix fast. Do not use those as a first-step scan.

### The wrong version

Do not fire the hops from a script that has already chosen every query:

```python
# Wrong: the path is fixed before any result is read
queries = [
    "SELECT domain, entity_id, resolution_status FROM web.domain_entity_bridge WHERE domain = 'attio.com'",
    "SELECT entity_id, name, website FROM companies.nucleus WHERE entity_id = 'spkco_...'",
    "SELECT entity_id, li_industry FROM companies.industry_keywords WHERE entity_id = 'spkco_...'",
    "SELECT source_entity_id, target_domain FROM companies.web_outlinks WHERE source_entity_id = 'spkco_...'",
    "SELECT url, title FROM web.pages WHERE domain = 'attio.com' LIMIT 50",
    "SELECT competitor_domain FROM companies.competitors WHERE entity_id = 'spkco_...'",
    "SELECT entity_id, li_headcount FROM companies.metrics WHERE entity_id = 'spkco_...'",
    "SELECT title FROM companies.jobs WHERE entity_id = 'spkco_...'",
    "SELECT title FROM companies.posts WHERE entity_id = 'spkco_...'",
    "SELECT round_type, amount_usd FROM companies.funding_rounds WHERE entity_id = 'spkco_...'",
]
for sql in queries:
    subprocess.run(["speaker", "query", sql])
```

That script has already chosen the hops, the identifiers, and the stop point. The loop exists so the next query is decided by the last result.

## Entry patterns

### Known company

Start with `companies.nucleus` if you have `entity_id`, or resolve a domain first:

```bash
speaker query "SELECT entity_id, name, website FROM companies.nucleus WHERE entity_id = 'spkco_...'"
```

Then hop by `entity_id`:

```text
companies.identifiers
companies.metrics
companies.industry_keywords
companies.jobs
companies.posts
companies.competitors
companies.funding_rounds
companies.web_outlinks
```

### Known person

Start with `people.nucleus` by `person_id`:

```bash
speaker query "SELECT person_id, first_name, last_name, professional_title FROM people.nucleus WHERE person_id = 'spkp_...'"
```

Then hop by `person_id`:

```text
people.contacts
people.roles_history
people.education
people.repos
```

### Known domain

Use the domain bridge, then carry `entity_id`:

```bash
speaker query "SELECT domain, entity_id, resolution_status FROM web.domain_entity_bridge WHERE domain = 'example.com'"
```

Use the same domain directly for web pages:

```bash
speaker query "SELECT url, title, desc FROM web.pages WHERE domain = 'example.com' LIMIT 20"
```

### Web evidence

Only enter `web.pages` by `domain` or a small `domain IN (...)` list. Selecting `text` is expensive; narrow first.

## Performance rules

Do:

```sql
WHERE person_id = '...'
WHERE entity_id = '...'
WHERE domain = '...'
WHERE entity_id IN (...)
WHERE domain IN (...)
```

Avoid as first-step broad scans:

```sql
-- huge full-text scan
FROM web.pages
WHERE lower(text) LIKE '%payments%'

-- graph-valid but not ORDER BY-prefix fast today
FROM people.nucleus
WHERE current_company_id = 'spkco_...'

-- graph-valid but not ORDER BY-prefix fast today
FROM people.roles_history
WHERE speaker_company_id = 'spkco_...'

-- broad joins before narrowing ids
FROM people.roles_history r
JOIN people.nucleus p ON p.person_id = r.person_id
```

Prefer two or three small ID hops over one large join.

## What to use when

The two nucleus tables are the heart of the graph:

- `people.nucleus` — source of truth for people in the professional world. Current snapshot: name, location, professional title, seniority, current company id/name, skills/signals.
- `companies.nucleus` — source of truth for companies/entities. Company profile: name, website, summary, keywords, headcount, location, reputation-style ranking signal.

Most other tables are flat sidecars or edge tables linked back to one of these nuclei by `person_id`, `entity_id`, or `domain`.

Company side:

- `companies.identifiers` — company identity resolution sidecar. Use when you have a website, LinkedIn URL/slug, social/profile URL, marketplace URL, or other public identifier and need to map back to `entity_id`. For pure domain → entity resolution, prefer `web.domain_entity_bridge` first.
- `web.domain_entity_bridge` — fast domain → `entity_id` resolver. Use when the starting point is a domain.
- `web.pages` — large crawled web corpus. Use for deep page evidence not already preprocessed: headings, metadata, page text, emails/phones/socials/tools/outlinks. Always enter by `domain` or small `domain IN (...)`.
- `companies.metrics` — quantifiable business signals: headcount, growth, traffic, SEO, hiring, reviews, ProductHunt/G2/Gartner, funding/M&A counts. Use to score, rank, or enrich known companies.
- `companies.industry_keywords` — richer industry/taxonomy/facet evidence than `companies.nucleus.keywords`. Use for industry/category research.
- `companies.jobs` — one row per job posting. Use to infer hiring focus, current initiatives, teams being built, and strategic direction.
- `companies.posts` — news/article mentions, not social posts. Use to see what companies are being talked about and find external signals.
- `companies.competitors` — preprocessed competitor-domain edges, mainly from SEO/competitive sources. Use for market maps and alternative-company discovery.
- `companies.funding_rounds` — one row per funding round. Use for funding history, latest round, investor display strings, and amount/date signals.
- `companies.web_outlinks` — page-level external outlink graph from known company websites. Use to understand ecosystems, partner/vendor/customer/content networks, and starting points for further web research.

People side:

- `people.contacts` — person identity/contact sidecar. Use after `person_id` to get LinkedIn slug, social handles, GitHub, websites, and emails where available.
- `people.roles_history` — one row per career position. Use for career paths, previous employers, current/past roles, and movement patterns such as “ex-bank people now in tech”. Prefer starting from `person_id`; company-only scans are graph-valid but not physically fast today.
- `people.education` — one row per education record/degree. Use after `person_id` for schools, degrees, fields of study.
- `people.repos` — GitHub repositories. Use to understand what a developer has published or to enter from GitHub `owner/repo`; person linkage is sparse.

## Limits and failure modes

Speaker is SQL-native, not magic. Big tables are real ClickHouse tables.

- Max returned rows: 100,000.
- Public query timeout: about 50 seconds server-side, 60 seconds through the API path.
- A `LIMIT 20` query can still timeout if it scans billions of rows.
- Timeout usually means the filter did not match the physical access path or the text scan was too broad.

If a query times out, simplify:

1. Start from a known `person_id`, `entity_id`, or `domain`.
2. Query one table.
3. Carry the key to the next table.
4. Avoid full text scans and broad joins.

## Main command

```bash
speaker query "SELECT ..."
```

Use `speaker help` for CLI commands.

more queries = more signal
