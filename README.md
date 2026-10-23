# NBA AI Agents

Daily NBA podcast generation using Google ADK, ESPN scoreboard data, Gemini speech synthesis, and Google Cloud Storage.

[Spotify](https://open.spotify.com/show/5u255pZEvJeOzKMWCuDQsP) · [RSS feed](https://damimartinez.github.io/nba-daily-summary-podcast/podcast/rss.xml) · [Original technical write-up](https://damimartinez.github.io/nba-podcast-using-adk/)

## Requirements and installation

- Python 3.11+ (CI tests 3.11–3.13), Poetry 2.5.1
- Google AI API access for text, Search grounding, and TTS
- Google Cloud credentials with upload and object-ACL permissions for the configured bucket

```bash
git clone git@github.com:DamiMartinez/nba-agents.git
cd nba-agents/nba-publisher-agent
poetry install
```

Configure these environment variables locally or through your CI secret store. Never commit credentials:

```bash
export GOOGLE_API_KEY="<your-google-ai-api-key>"
export GOOGLE_GENAI_USE_VERTEXAI="0"
export GOOGLE_CLOUD_PROJECT="<your-project-id>"
export GOOGLE_APPLICATION_CREDENTIALS="<absolute-path-to-service-account-json>"
```

The upload tool currently defaults to the existing `nba_daily_summary_podcast_audios` bucket and makes objects public. Configure the bucket argument in the tool if deploying elsewhere; review its public-access policy first.

### Models

Defaults, checked against [Google's model catalog](https://ai.google.dev/gemini-api/docs/models) and [TTS guide](https://ai.google.dev/gemini-api/docs/speech-generation) on October 21, 2026:

| Setting | Default |
| --- | --- |
| `NBA_AGENT_MODEL` | `gemini-3.8-flash` |
| `NBA_TTS_MODEL` | `gemini-3.8-flash-tts` |
| `NBA_TTS_VOICE` | `Rasalgethi` |

Text/search/podcast agents share the text model setting. TTS uses the Interactions API with verbatim transcript input and WAV output (GenAI SDK 2.32+). Model availability, billing, and quotas must be checked for your account. The TTS override must support this Interactions API contract; older 2.5 TTS IDs are **not** drop-in replacements.

## Run

```bash
poetry run python run_agent.py
# Historical or explicitly dated edition:
poetry run python run_agent.py --edition-date 2026-10-21
# No LLM calls, uploads, or Google credentials required:
poetry run python run_agent.py --collect-only --edition-date 2026-10-21
# Optional interactive ADK UI (does not use the runner's preflight/wait loop):
poetry run adk web
```

### What “last night” means

An edition dated **D in America/New_York (Eastern Time)** covers:

- **Results:** games whose scheduled tip-off falls on **D−1 in America/New_York**.
- **Upcoming schedule:** games whose scheduled tip-off falls on **D in America/New_York**.
- **Display:** full dates and timezone-aware times in **America/New_York**, labeled ET (EST in winter / EDT in summer).
- **Episode date, audio filename, report date, and RSS date selection:** the same Eastern edition date.

For example, the January 2 Eastern edition includes January 1 afternoon games **and** the January 1 10:30 PM ET game, even though the latter's UTC timestamp falls on January 2. It previews games starting January 2 Eastern time. A game finishing after midnight remains attached to its tip-off date. A rescheduled game follows the source's updated tip-off date.

All user-facing dates/times and clock reads use `America/New_York`, independent of the host's timezone. `zoneinfo` applies US daylight saving automatically; summer is EDT, not EST. Europe changing clocks has no effect. UTC source timestamps are retained only for internal auditing; never narrate them or apply fixed offsets.

### Collection and failure behavior

1. Freeze the edition date at startup.
2. Query ESPN's NBA scoreboard for the target date and both adjacent dates, with an explicit result limit. Filter using the actual Eastern tip-off date; deduplicate by game ID.
3. Include all season types exposed by the source: no hard-coded season year or regular-season/playoffs-only filter. Preserve scores, points leaders, game status, and UTC/Eastern source timestamps. Completed games also fetch structured box scores and recap text; structured player statistics and starter roles override stale recap/search claims. Unavailable details are flagged and extra numerical claims must be omitted.
4. Retry transient HTTP failures. Invalid responses, failed adjacent queries, and malformed events are errors, **not** evidence of no games.
5. If a result is still scheduled, delayed, or live, poll every five minutes for up to 30 minutes; fail without generating/uploading audio if it remains unresolved. Postponed/cancelled games remain visible but do not require a final score.
6. Freeze both successful slates in ADK session state before invoking the LLM. Search only supplies additional highlights.
7. Require both a final root-agent response and a confirmed upload before returning exit code 0.

ESPN's public scoreboard is undocumented and has no availability or completeness guarantee. The current collector fails closed on observable errors but cannot detect a valid-looking response that silently omits an event. See [the review](docs/code-review.md) for remaining risks.

### Outputs

Inside `nba-publisher-agent/`:

- `reports/nba_YYYY-MM-DD.json`: frozen source snapshot, including game IDs, collection timestamps, and queried dates.
- `reports/nba_YYYY-MM-DD.md`: final agent report after confirmed publication.
- `reports/nba_YYYY-MM-DD.script.txt`: exact narration submitted to TTS (saved before the API request).
- `audios/nba_daily_summary_podcast_YYYY-MM-DD.wav`: generated audio.

Local output folders are ignored by Git. Daily Actions runs retain reports/audio as artifacts. This repository uploads audio; it does **not** implement the downstream RSS/Spotify feed updater. Re-running an edition can replace its audio object; cross-run idempotency is not yet implemented.

## Development

```bash
cd nba-publisher-agent
poetry check --lock
poetry run pytest --cov=nba_publisher_agent --cov=run_agent --cov-report=term-missing
poetry run black --check .
poetry build
```

Tests mock network, LLM, and storage calls; they require no credentials. Coverage includes midnight/date boundaries, DST transitions and mismatch weeks, duplicate games, all season types, incomplete results, postponed/cancelled games, source failures, WAV validation, and publication failure handling.

`poetry.lock` pins the complete dependency graph. To update it deliberately, edit dependency constraints, run `poetry lock`, and rerun checks. Unused NBA API, AI Platform/deployment extras, and unrelated ML/test dependencies were removed; `python-dotenv` is now explicit.

## Automation

- `.github/workflows/tests.yml`: tests, formatting, dependency validation, and package build on pushes/PRs.
- Generation and publication have **no built-in GitHub cron schedules**. An external system or a manual `workflow_dispatch` starts them. Both must be enabled for dispatch to work; enabling them after the schedule-removal PRs are merged does not restore cron execution.
- The external caller should dispatch generation first and publication after it succeeds. The publisher can also be dispatched concurrently and will wait up to **90 minutes** for the canonical audio upload; a missing upload after the deadline fails visibly.
- Pass the same **Eastern** `edition_date` to both workflows. If omitted, each chooses today's date in **America/New_York**, independent of the external caller's timezone. Explicit dates are recommended so a dispatch spanning midnight cannot select mismatched editions.
- Scheduling belongs to the external system. Episode dates, game times, narration, filenames, and RSS dates remain Eastern. Do not reintroduce GitHub cron without approval.
- Daily workflow secrets: `GOOGLE_API_KEY` and `GOOGLE_APPLICATION_CREDENTIALS` (the JSON credential document). Temporary credential files are permission-restricted and cleaned up.

## Structure

```text
nba-publisher-agent/
  run_agent.py                   # deterministic collection, wait loop, runner
  nba_publisher_agent/
    agent.py                     # research/production/podcaster agents
    config.py                    # overridable model defaults
    game_data.py                 # shared date-safe scoreboard collector
    tools/                       # ADK wrappers, audio generation, upload
  tests/
  pyproject.toml
  poetry.lock
docs/code-review.md               # findings and follow-up priorities
```

## Author and contributing

Author: [DamiMartinez](https://github.com/DamiMartinez) (Damian Martinez Carmona).
Contributions are welcome via pull request; include tests for behavioral changes.

## License

[MIT](LICENSE).
