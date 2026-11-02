# Run log (all times America/New_York, ET)

| When (ET) | What | Result |
|---|---|---|
| 2026-11-01 | Harvest source registry: 4 Project Gutenberg books, rights checked (dc.rights + gutendex) | `_config/registries/harvest_sources.json` |
| 2026-11-02 14:31–14:32 | Book harvest round 4 (spaCy en_core_web_sm + nych3), 29,377 sentences | 3,542 new candidate loops (`shared/data/harvest/runs/20261102T143121.json`, not shipped) |
| 2026-11-02 | Gold set v1, 300 sentences, agent-graded (pending human review); nych3-eval | sentences 146/132/22 correct/partial/wrong |
| 2026-11-02 14:25–15:20 | tech.ui polite scrape (UA NYCH-research-bot/0.1, robots.txt, >=1.5 s/host) | Microsoft 1,500, Claude 367, YouTube 436, Android 222; Apple 29 (HTTP 429) |
| 2026-11-02 15:20–16:40 | Background Google scrape continued (Gemini, Chrome), finished on its own | Gemini 136, Chrome 197 (total 2,887 articles) |
| 2026-11-02 15:28 | tech.ui spot check, 40 random actions, agent-graded | 21 correct / 6 partial / 13 wrong |
| 2026-11-02 16:04 | First tech.ui ingest into knowledge-graph store (2,637 articles) | 81 + 33,053 loops, 56,116 SourceRefs; commit 9fb844f |
| 2026-11-02 16:55 | Rebuild tech.ui from all 2,887 cached articles | 65,929 actions; top-10/25/50/100 = 55.9/79.7/93.1/96.3% |
| 2026-11-02 17:00–17:15 | Re-ingest attempts OOM-killed (Kuzu memory growth on one connection) | restored pre-tech.ui backup; fix: reconnect per 500-loop batch + 2 GiB pool |
| 2026-11-02 17:30 | tech.ui re-ingest (from pre-tech.ui backup) | 81 + 36,445 loops, 63,487 SourceRefs; store 40,071 loops |
| 2026-11-02 | pytest knowledge-graph | 143 passed |
