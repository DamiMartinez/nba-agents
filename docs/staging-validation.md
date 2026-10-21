# Eastern-time staging validation — October 21, 2026

## Result

The local staging sequence passed in the requested order: **script → audio →
GCS staging upload → RSS builder on a feed copy**. No live RSS publication or
GitHub-hosted workflow execution was performed.

## 1. Data and script

- Edition timezone: `America/New_York`.
- Results date: October 20, 2026; all **3** games included once:
  - Detroit 121, Boston 113.
  - Philadelphia 106, New York 100.
  - Oklahoma City 116, San Antonio 104.
- Upcoming date: October 21, 2026; all **11** games included once, from
  **7:00 PM through 10:30 PM EDT**.
- The real ADK agents generated the script with audio/upload tools intercepted.
- A separate extraction call received the narration and team-to-ID mapping,
  **not expected scores, schedule times, or player statistics**. Deterministic
  comparisons then matched all 3 results, 11 scheduled start times, and
  **57 extracted player-stat/role claims** against the frozen source snapshot.
- Manual script inspection found no remaining Madrid dates/times.
- Script SHA-256:
  `a3741a92381e8e56949ca9d80fb0f9478896e315fa2ecb45fd79b4b1095fffde`.

The earlier review independently compared the same game's scores and schedule
against [CBS's scoreboard](https://www.cbssports.com/nba/scoreboard/20261020/)
and [schedule](https://www.cbssports.com/nba/schedule/20261021/).

## 2. Audio

The actual production audio tool generated from that exact approved script
using `gemini-3.8-flash-tts` and the `Rasalgethi` voice, in an isolated folder.

- Duration: **189.6 seconds** (approximately 3:10).
- WAV: 24 kHz, mono, 16-bit PCM; **9,106,918 bytes**.
- Speech rate: approximately 171 words/minute.
- RMS: −17.78 dBFS; peak 0.8781; no clipped samples.
- A fresh audio-only transcription received **no expected script or source
  scores**. Its extracted claims again matched all 3 results, 11 start times,
  and 57 player-stat/role claims. Introduction and conclusion were preserved.
- WAV SHA-256:
  `c25e8814e55c312fa36b3751ebcf59d2a45a711a52f2282b49c2ce28e5361863`.

This validates technical integrity and spoken factual content, not subjective
human listening quality. The audio is available for listening below.

## 3. GCS handoff

The real upload tool uploaded a deliberately non-production filename:

[Listen to the staging audio](https://storage.googleapis.com/nba_daily_summary_podcast_audios/staging_nba_daily_summary_podcast_2026-10-21_17108c41.wav)

A public download matched the local WAV byte-for-byte (SHA-256 above). The
publisher's canonical `nba_daily_summary_podcast_YYYY-MM-DD.wav` lookup cannot
select this `staging_...` filename. No production object was overwritten.
The staging object remains available; it has not been deleted.

A bucket-metadata preflight was denied, but actual object upload, public ACL,
and public download all succeeded. Bucket-metadata read permissions are not
required by the production upload path and were not broadened.

## 4. RSS workflow check

Executed the publisher workflow's **actual inline Python**, with only its audio
URL redirected to the staging object, in a temporary directory containing a copy
of the real RSS feed. No Git commit/push step was executed.

Checks passed after correcting the zero-byte enclosure bug:

- Exactly one episode added for the Eastern edition date.
- Enclosure URL and GUID select the staging audio.
- MIME type `audio/wav`; enclosure length **9,106,918** (not zero).
- iTunes duration `00:03:09` (integer-second truncation of 189.6 seconds).
- Publication timestamp has the correct EDT offset, `-0400`.
- A repeated run leaves the feed unchanged and creates no duplicate.
- The live repository's RSS file remains byte-for-byte unchanged.

Additional publisher changes bound HTTP reads, fail on non-404 HTTP errors,
remove temporary downloads, place new episodes before existing ones even if
metadata was missing, explicitly grant the workflow's needed write permission,
and serialize publisher runs.

## Automated checks

- Initial staging suite: **62 producer tests** and **8 publisher tests** passed (93% measured producer coverage).
- Scheduling follow-up: **64 producer tests + 11 publisher tests passed**, including Madrid 11:00/DST policy and upload-polling/deadline regression tests.
- Producer formatting, lockfile validation, wheel/sdist build: passed.
- `actionlint` v1.7.12: all four edited/added workflow files passed structural
  and expression validation (`shellcheck` integration disabled for this run).
- Redacted secret scans are performed separately before any commit/push.

## Still pending: real GitHub Actions execution

Both remote scheduled workflows are **manually disabled**, and the code changes
remain on local task branches. The staging checks do not prove that installation,
GitHub Secrets, runner permissions, Git commits/pushes, or Pages deployment work
on GitHub-hosted runners.

The user subsequently approved pushing the task branches, opening PRs, enabling
daily workflows, and changing the schedule to 11:00 Europe/Madrid. Both workflows
now use native Madrid-time scheduling; the publisher waits up to 90 minutes for
its matching Eastern-date audio. Actual publication follows generation.

Both PRs must first be merged with explicit approval, then the daily workflows can
be enabled against the new default-branch code. Do not merge without that approval.
After activation, verify GitHub logs, output artifacts, and edition-date handoff.

## Local evidence

Ignored, local-only artifacts under `nba-publisher-agent/reports/staging/`:

- `edition.json`, `podcast_script.txt`, `agent_report.md`.
- `script_manifest.json`, `script_audit.json`, `extracted_claims.json`.
- `audio_manifest.json`, `audio_transcript.txt`, `transcript_audit.json`.
- `upload_manifest.json`, `preview_rss.xml`, `rss_workflow_audit.json`.
- `audio-test/audios/nba_daily_summary_podcast_2026-10-21.wav`.

The old Madrid-stage evidence is archived separately and must not be reused.
LLM-based extraction/transcription can itself make mistakes; this single live
sample is not a proof that every future generated script will be complete.
