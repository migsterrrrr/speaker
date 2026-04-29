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
