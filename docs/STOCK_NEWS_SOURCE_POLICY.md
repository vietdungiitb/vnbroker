# Stock News Source Policy

Last updated: 2026-04-11

## 1) Purpose

Define source governance for stock news ingestion in vnbroker:

- Legal and attribution baseline
- Technical reliability requirements
- Priority and rollout rules

## 2) Source tiers

## Tier A (production first)

- `vci` company news
- `kbs` company news
- `rss_cafef`
- `rss_vneconomy`

## Tier B (stabilize before broad rollout)

- `tcbs` company news
- `vietstock` RSS (when stable)
- `tinnhanhchungkhoan` RSS (when parser stable)

## Tier C (strategic expansion)

- Licensed/commercial feeds
- Official exchange/issuer channels with formal terms

## 3) Mandatory metadata per record

- `source`
- `url`
- `published_at`
- `fetched_at`
- `source_article_id` when available

## 4) Usage constraints

- Respect source terms and robots policies.
- Keep source attribution in all downstream outputs.
- If full-text rights are unclear, store summary/snippet only.

## 5) Operational thresholds

- Parse success rate >= 95% over rolling 24h.
- Duplicate ratio <= 25% after dedup.
- Broken-link ratio <= 5%.

If thresholds are violated, source enters cooldown and is deprioritized in AUTO routing.

## 6) Review cadence

- Weekly technical health review.
- Monthly legal/policy review for external media feeds.
