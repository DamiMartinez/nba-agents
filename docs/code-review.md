# Repository review — October 21, 2026

## Findings addressed

| Priority | Finding | Change |
| --- | --- | --- |
| High | Results used host-local `date.today()` while prompts claimed Madrid time; schedule used a different clock. | One Eastern (America/New_York) edition date frozen per run, shared by collection, narration, filenames, and the downstream RSS publisher. |
| High | Madrid date filtering/fixed EST→UTC+1 conversions split overnight games and fail around DST. | Query adjacent source dates, filter aware tip-off timestamps in America/New_York, deduplicate IDs, render America/New_York offsets with `zoneinfo` (EST/EDT), never fixed-offset or Madrid output. |
| High | NBA stats exceptions were swallowed and returned as an empty result list. | Observable source failures and invalid events fail the collection; no audio production starts from a failed preflight. |
| High | Early cron could run before late games/overtime ended, especially at 07:00 Madrid in winter. | Start both daily workflows at 11:00 Europe/Madrid using native timezone/DST support. Generation waits up to 30 minutes for unresolved results; the publisher waits up to 90 minutes for the successful audio upload. Podcast dates/times remain Eastern. |
| High | Results queried only playoffs/regular season and stopped at the first nonempty response; schedule hard-coded season 2025. | Shared scoreboard collector with no season-year/type filter. Includes preseason, play-in, postseason, and other events returned by ESPN. |
| Medium | League game log returned team rows, not one matchup with both scores; top scorers were promised but not collected. | Normalize one game per ID, paired teams/scores, explicit statuses, points leaders, and completed-game box scores with starter roles. Structured stats override stale prose. |
| Medium | No lockfile and mostly unused dependencies; dotenv only arrived transitively; package referenced a nonexistent README. | Current directly used dependencies, explicit dotenv, PEP 621 metadata, committed Poetry lockfile, build validation. |
| Medium | Old hard-coded text/TTS models; blocking synchronous API call inside async audio tool. | Configurable stable Gemini 3.8 Flash/Flash TTS defaults; async Interactions API, response validation, bounded TTS request timeout. |
| Medium | No final response still returned a successful process result; upload failure could be treated as success by the LLM. | Require final root response and upload state set by the upload tool. Restrict upload input to the current generated audio path. |
| Medium | Model received fresh independent tool responses and no durable source evidence. | Freeze both slates in session state; persist dated JSON source snapshot and final report. |
| Medium | No automated tests/build checks; Actions cache had no lockfile key to hash. | Regression suite, Python CI matrix, pinned Poetry, locked dependency installation, updated Actions versions. |
| Low | Inaccurate README claims about saved text reports/RSS automation and schedule timing. | Document actual outputs, data policy, configuration, failure modes, schedule, and downstream boundary. |

## Source choice and trade-offs

The original `stats.nba.com` endpoints are prone to timeouts/access restrictions and the league game-log feed can lag a live scoreboard. The official NBA CDN schedule returned HTTP 403 during this review. ESPN's public scoreboard was reachable and supplied dates, scores, status, season metadata, and leaders without an API key, so both tools now use it consistently.

Adjacent-date requests deliberately over-fetch, then use timestamps rather than assuming a provider query date is already in the desired timezone. Every adjacent request must succeed. Duplicate IDs are collapsed; later responses replace earlier observations. A tip-off date, not a game's completion date, determines its slate. This covers ordinary overnight NBA scheduling without excluding US afternoon games.

**Limitation:** ESPN is an undocumented third-party API, not an official completeness guarantee. Valid-looking missing events, retroactive source corrections, unusual after-midnight Eastern rescheduling, and incorrect source timestamps need operational oversight. No secondary-source reconciliation is claimed.

## Recommended follow-ups (not implemented)

1. **High — Independent completeness reconciliation.** Compare source game IDs/matchups against an official NBA or contracted schedule feed. Alert on expected-vs-returned count differences and unresolved data. Contract-test saved real-world source fixtures regularly. Avoid using LLM search as the authority for missing scores.
2. **High — Machine-validated editorial coverage.** The prompt now explicitly requires every returned game, but an LLM can still omit one in its narration. Produce a structured report with a game-ID list, validate exact coverage against the frozen snapshot, then render the narration deterministically. That is stronger than prompt-only validation.
3. **High — Publication idempotency and recovery.** Add a durable ledger keyed by edition/game IDs, atomic generation/upload stages, and an explicit replace/backfill policy. Current Actions concurrency prevents simultaneous runs but not duplicate sequential publication or overwrites. API failure after an upload can also leave a published object despite a failed overall run.
4. **High — Cloud authentication and public-access policy.** A locally ignored service-account JSON file exists; it was not opened or changed. Keep it outside the repo and consider short-lived Workload Identity Federation. The upload tool still requires a credential-file environment variable and calls `make_public()`, which fails on uniform bucket-level access or public-access prevention. Prefer ADC plus an explicitly configured bucket policy or signed URLs; coordinate changes with the downstream RSS consumer.
5. **Medium — Long scripts and TTS recovery.** Large NBA slates may exceed TTS limits. Add sentence-aware chunking, retry/backoff for generation, WAV concatenation, duration/size limits, and atomic local output. Do not blindly retry cloud publication without an idempotency key.
6. **Medium — Observability.** Add structured logs, metrics for expected/completed games, source latency, data freshness, model usage/cost, alerting for failed/late runs, and persisted partial-source diagnostics. Errors currently avoid echoing potentially sensitive upstream bodies but offer limited diagnostics.
7. **Medium — Separate editorial text from confirmation.** ADK's `summary_report` output is the final root response; the prompt still combines report, script, and final confirmation. Persist separate typed artifacts for each rather than relying on a single free-form output key.
8. **Medium — ADK 2 modernization.** `AgentTool` remains compatible but the current SDK recommends single-turn subagents. Consider replacing the extra podcast LLM with deterministic generation/upload code, and cap LLM calls/cost per edition.
9. **Low — Dependency/CI maintenance.** Add scheduled Dependabot/Renovate updates and vulnerability auditing. Pin third-party Actions by reviewed commit SHA if supply-chain immutability is required. The package currently permits Python versions newer than those in the CI matrix.

## Validation scope

- Automated tests exercise network/source failures, timezone boundaries, DST, season types, deduplication, unfinished games, source snapshot reuse, audio response validation, and publication success/failure without making paid calls.
- A live data-only collection for edition `2026-10-21` successfully collected 3 games for Eastern date `2026-10-20` plus the upcoming slate.
- Dependency resolution, installed agent imports, formatting, and package build are checked locally; GitHub CI defines additional Python-version coverage.
- A subsequent credentialed script-only test confirmed model access and checked 3 results, 11 upcoming games, and 44 extracted player-stat/role claims. It exposed stale recap statistics and an inferred starter/bench role; structured box-score enrichment and stricter source rules were added.
- That script used the former Madrid presentation and is superseded by the user's Eastern-only requirement. Its approval must NOT be reused for a new script/audio run.
- Testing subsequently resumed under the Eastern-only requirement: the regenerated script and audio passed checks for 3 results, 11 upcoming games, and 57 extracted stat/role claims. A real staging upload/download matched the audio bytes, and the actual RSS builder passed on a copied feed after fixing zero-byte enclosure metadata. See [the staging report](staging-validation.md) for evidence and limitations.
- Both remote scheduled workflows remain manually disabled. No live RSS update, GitHub-hosted test run, merge, or production end-to-end publication has occurred.

## References

- [Google Gemini models](https://ai.google.dev/gemini-api/docs/models)
- [Google TTS guide](https://ai.google.dev/gemini-api/docs/speech-generation) — Interactions API and unary WAV output
- [ESPN NBA scoreboard](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard)
- [Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html)
- Package versions resolved from PyPI on October 21, 2026; exact versions/hashes are in `nba-publisher-agent/poetry.lock`.
