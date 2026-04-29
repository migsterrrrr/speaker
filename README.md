# Speaker

SQL-native professional intelligence for agents.

Speaker lets agents query for professional intel directly from the coding harness of your choice. Add it to Claude, Codex, Pi, or any agent shell; your agent writes SQL, reads the results, and keeps exploring until it has the answer.

```text
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

## Why Speaker

Agents should not have to scrape the web from zero for every business question.

Speaker gives them live SQL surfaces over a professional graph:

- **people** — current professional profiles, contacts, career history, education, GitHub repos
- **companies** — company profiles, identifiers, metrics, taxonomy, jobs, posts, competitors, funding
- **web** — domain resolution and page-level web evidence

The graph is flat on purpose. Query one table, carry `person_id`, `entity_id`, or `domain`, then hop.

## Use it

```bash
# Install
# Uses /usr/local/bin if writable, otherwise falls back to ~/.local/bin
curl -sL https://raw.githubusercontent.com/migsterrrrr/speaker/master/cli/install.sh | sh

# Install to a custom prefix (npm-style: PREFIX/bin)
curl -sL https://raw.githubusercontent.com/migsterrrrr/speaker/master/cli/install.sh | PREFIX="$HOME/.local" sh

# Install to an exact bin dir
curl -sL https://raw.githubusercontent.com/migsterrrrr/speaker/master/cli/install.sh | BINDIR="$HOME/bin" sh

# Pi
pi install git:github.com/migsterrrrr/speaker
```

Then:

```bash
speaker login <api-key>
speaker query "SELECT count() FROM companies.nucleus"
speaker schema
```

## The graph keys

| Key | Meaning | Use it to hop between |
|---|---|---|
| `person_id` | Speaker person id | `people.nucleus`, `people.contacts`, `people.roles_history`, `people.education`, `people.repos` |
| `entity_id` | Speaker company/entity id | `companies.nucleus`, company sidecars, people current/role company ids, resolved web pages |
| `domain` | normalized website/domain | `web.domain_entity_bridge`, `web.pages`, company websites, competitor/outlink domains |

Core rule:

```text
hops, not broad joins
```

## Public tables

### People

| Table | What it is for |
|---|---|
| `people.nucleus` | source of truth for professional people; current snapshot |
| `people.contacts` | LinkedIn/social/GitHub/web/email fields where available |
| `people.roles_history` | one row per career position |
| `people.education` | one row per education record/degree |
| `people.repos` | GitHub repositories with optional person link |

### Companies

| Table | What it is for |
|---|---|
| `companies.nucleus` | source of truth for companies/entities; profile snapshot |
| `companies.identifiers` | website/social/profile/marketplace identifiers; identity resolution sidecar |
| `companies.metrics` | headcount, growth, traffic, SEO, hiring, reviews, funding/M&A metrics |
| `companies.industry_keywords` | rich taxonomy and industry/facet signals |
| `companies.jobs` | one row per job posting; hiring and strategic initiative signal |
| `companies.posts` | news/article mentions, not social posts |
| `companies.competitors` | competitor-domain edges from competitive/SEO signals |
| `companies.funding_rounds` | one row per funding round |
| `companies.web_outlinks` | page-level external outlinks from company websites |

### Web

| Table | What it is for |
|---|---|
| `web.domain_entity_bridge` | fast domain → `entity_id` resolver |
| `web.pages` | crawled page evidence; enter by `domain` |

## Schema

Curated schema docs include graph keys, ClickHouse access notes, and per-column fill rates:

```bash
speaker schema
speaker schema companies.nucleus
speaker schema people.nucleus
speaker schema web.pages
```

Raw DB metadata:

```bash
speaker query "DESCRIBE companies.nucleus"
```

For agents, the installed skill file is the operational onboarding doc:

```text
~/.speaker/SKILL.md
```

## Query limits

Speaker is SQL-native, not magic. Big tables are real ClickHouse tables.

- Max returned rows: 100,000
- Public query timeout: about 50 seconds server-side, 60 seconds through the API path
- A `LIMIT 20` query can still timeout if it scans billions of rows

Avoid broad first-step scans like:

```sql
FROM web.pages WHERE lower(text) LIKE '%payments%'
```

Prefer exact key hops:

```sql
WHERE person_id = '...'
WHERE entity_id = '...'
WHERE domain = '...'
```

See [QUERY_LIMITS.md](QUERY_LIMITS.md) for details.

## Contribute

Speaker is an open-source CLI and schema layer over a hosted professional graph.

Useful contributions:

- better schema docs
- safer query recipes
- example workflows
- integrations and agent skills
- new open tables that can join the mesh

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Philosophy

Every table is a doorway.

The insight is never in one table — it is in the connections.

Contribute selfishly, benefit collectively.

more queries = more signal
