# Speaker

Professional intelligence for agents.

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

818M people. 3.7M companies. Connected by career moves, skills, education, web links, code, news. 10 tables. Enter anywhere.

## Use it

```bash
# Pi
pi install git:github.com/speakerdata/speaker

# Any agent — read SKILL.md, query via bash
ssh root@endpoint "clickhouse-client --query 'SQL'"
```

## The mesh

```
👤 people.main          📋 people.career        🎓 people.education
📡 people.contact       ⚡ people.repos

🏢 companies.main       💼 companies.jobs        📰 companies.news

🕸️ web.links             📄 web.pages
```

Every edge is a hop. Carry IDs between queries. The insight is never in one table — it's in the connections.

## Open data

The two nuclei (`people.main`, `companies.main`) are proprietary and hosted.
Everything else is open — [schemas](tables/), [pipelines](pipelines/), and data ([HuggingFace](https://huggingface.co/speakerdata)).

## Contribute

Add a table to the mesh. See [CONTRIBUTING.md](CONTRIBUTING.md).

```
1. Fork → 2. Add schema + pipeline → 3. PR → 4. Your table joins the mesh
```

The best tables are ones you need. Build it for yourself. The mesh makes it valuable for everyone.

## Philosophy

The insight is never in one table — it's in the connections.
Contribute selfishly, benefit collectively.
The mesh makes every table more valuable than it would be alone.

more queries = more signal
