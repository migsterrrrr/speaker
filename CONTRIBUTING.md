# Contributing a Table

The mesh grows through contributions. Add a table, connect it, everyone benefits.

## How

1. Fork this repo
2. Copy `contrib/_template/` to `contrib/your-table/`
3. Fill in `main.yaml` — your schema
4. Add `pipeline.py` (or `.sh`) — builds from a public data source
5. PR

## Rules

- **Must connect.** At least one column must link to `people.main.speaker_person_id` or `companies.main.entity_id`. Without a connection, it's a standalone dataset, not a mesh node.
- **Public data source.** The pipeline must build from data anyone can access.
- **Reproducible.** Someone else can run your pipeline and get the same result.
- **English canonical names.** Column descriptions and values in English where possible.

## What happens after merge

- Your pipeline runs on the central ClickHouse
- The table appears in the mesh
- Every agent sees it immediately
- Parquet export published to HuggingFace
- You're listed as maintainer

## What makes a good contribution

Tables that create new connections in the mesh:

| Table idea | Connects via | Source |
|---|---|---|
| Conference speakers | person_id | Public conference sites |
| Patents | person_id + entity_id | USPTO / EPO |
| Funding rounds | entity_id | Public filings |
| Research papers | person_id | Semantic Scholar / arXiv |
| Regulatory filings | entity_id | Public registries |
| Podcast appearances | person_id | Public RSS feeds |

The best tables are ones YOU need. Build it for yourself. The mesh makes it valuable for everyone.
