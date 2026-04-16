---
name: speaker
description: "B2B people and company intelligence through the Speaker CLI. Use for people lookup, company research, competitive analysis, and market exploration across the mesh."
---

# The Mesh

```
         ⚡  📡  🎓  📋
          ╲  │  │  ╱
           ◉ people ◉
               ║
            🕸️─╬─📄
               ║
           ◉ companies ◉
          ╱  │  ╲
        📰  💼  📋
```

```
👤 people.main          📋 people.career        🎓 people.education
📡 people.contact       ⚡ people.repos

🏢 companies.main       💼 companies.jobs        📰 companies.news

🕸️ web.links             📄 web.pages
```

10 tables. 0 cost per query. Millisecond responses.

## Start here if you're lost

```bash
speaker help
speaker mesh
speaker schema people.main
```

## Core rule

**Hops, not joins.**

Query one table, carry the right key forward, then hop to the next table.

The most important graph keys are:
- `people.main.speaker_person_id`, person nucleus id
- `companies.main.entity_id`, company nucleus id
- `companies.main.website` / `*.domain`, fallback company hop when ids are missing

Use `speaker schema <database.table>` to see hop keys for a table.

## Schema first

Use curated schema docs before querying:

```bash
speaker schema people.main
speaker schema companies.main
speaker schema web.pages
speaker schema --all
```

If you need the raw database metadata:

```bash
speaker query "DESCRIBE people.main"
```

## Query loop

SCOPE → SCHEMA → CONTEXT → EXPLORE

1. Scope the goal
2. Read the relevant schema docs
3. Find the right graph key
4. Query one table
5. Carry the key forward
6. Hop to the next table
7. Repeat until the goal is met

## Explore pattern

- **broad**: what is in this table?
- **narrow**: one person or company, go deep
- **lateral**: carry a key and hop to a related table

Typical loop:

- find a company in `companies.main`
- carry `entity_id` or `website`
- hop to `companies.jobs`, `companies.news`, `people.main`, or `web.links`

Or:

- find a person in `people.main`
- carry `speaker_person_id`
- hop to `people.career`, `people.education`, `people.contact`, or `people.repos`

## Main command

Use:

```bash
speaker query "SELECT ..."
```

Use `speaker help` if you need a refresher on commands.

more queries = more signal
