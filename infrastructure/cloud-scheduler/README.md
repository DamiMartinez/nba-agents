# Cloud scheduling for the NBA podcast

Google Cloud Scheduler starts `orchestrator.yaml` daily at **11:00 Europe/Madrid**.
Google Cloud Workflows dispatches `DamiMartinez/nba-agents/daily-agent.yml` on
`main`, waits for that exact run to succeed, then immediately dispatches
`DamiMartinez/nba-daily-summary-podcast/publish_podcast.yml` on `main` and monitors it.
Both receive one frozen `edition_date` chosen in **America/New_York**.

No GitHub cron, local computer, LLM, container image, or continuously running
server is needed for orchestration. Madrid DST follows Scheduler's timezone.
11:00 is the dispatch target; Scheduler delivery and GitHub runner queues can delay it.

## Deploy

Prerequisites: authenticated `gcloud`, project billing, and permissions to enable
APIs, manage the listed resources, grant resource IAM, and act as service accounts.
Use your approved project; do not change the global gcloud project setting.

```bash
PROJECT_ID=YOUR_PROJECT_ID bash infrastructure/cloud-scheduler/deploy.sh
```

Default region: `europe-west1`. Set `REGION` consistently to override it.
The deployment creates:

- Workflow `nba-daily-orchestrator` with call logging disabled and BASIC history.
- Scheduler job `nba-daily-1100-madrid`, initially **PAUSED**, with automatic
  Scheduler retries disabled (the workflow handles safe read retries itself).
- An empty Secret Manager secret, `nba-github-actions-token`.
- Separate `nba-orchestrator` and `nba-scheduler` service accounts.
- A private `PROJECT_ID-nba-orchestration-state` bucket with uniform access and
  public access prevention. This is separate from the public audio bucket.

Runner IAM is limited to reading this secret and creating immutable state objects.
Scheduler needs a custom `nbaWorkflowStarter` role containing only
`workflows.executions.create`. Google grants this at project scope: it can start
other workflows in the same project, but cannot read, cancel, or edit them or
read the GitHub secret. Deployment skips this grant unless explicitly authorized
with `AUTHORIZE_PROJECT_START_ROLE=true`. No service-account
keys are created. Re-running deployment intentionally pauses the schedule again.

## One-time GitHub credential

Create a **fine-grained personal access token** in GitHub Settings > Developer
settings > Personal access tokens > Fine-grained tokens. Choose resource owner
`DamiMartinez`, **only** the two NBA repositories, and **Actions: read and write**
(plus automatically granted Metadata: read). Set an appropriate expiration and
renew it before expiry. Do not use the broad token from `gh auth token`.

In Google Secret Manager, open `nba-github-actions-token`, choose **New version**,
and enter the token there. Do not paste it into chat, shell arguments, source,
environment files, or logs. The secret stays empty until this step is completed.
Credential expiration or revoked permissions cause visible workflow failure.

## Validate and activate

Set `PROJECT_ID` and `REGION` in your shell (same values as deployment), then:

```bash
gcloud workflows run nba-daily-orchestrator --project="$PROJECT_ID" \
  --location="$REGION" --data='{"dry_run":true}'
```

A successful result is `status: preflight_passed`. This reads workflow metadata
and active-run lists for both repositories. It does **not** dispatch workflows,
write daily claims, generate audio, or modify the feed. It checks authenticated
read access; Actions write permission must also be configured on the token.
Preflight refuses to proceed while either production workflow is disabled or active.
Both main-branch workflow files must remain dispatch-only; deployment does not
edit them or turn GitHub schedules back on.

Only after preflight passes, resume the daily schedule:

```bash
gcloud scheduler jobs resume nba-daily-1100-madrid --project="$PROJECT_ID" \
  --location="$REGION"
```

For an explicitly approved real test, execute the workflow without `dry_run`.
That dispatches production generation/publication and can incur their normal costs.
Do not mistake a successful Scheduler HTTP request for successful publication:
it only means Workflows accepted an execution.

## Failure and duplicate handling

- Each edition is atomically claimed with a Storage `ifGenerationMatch=0`
  precondition **before** generation. Duplicate deliveries cannot dispatch it again.
- Failed/uncertain claims and dispatch POSTs are never automatically retried.
  Safe GitHub GETs use bounded transient retries. Returned exact run IDs and URLs
  are persisted under `runs/EDITION/REPOSITORY.json`, without credentials.
- Non-success generation, read failures, and two-hour monitoring deadlines stop
  execution before publication. Monitoring stops after two hours per workflow;
  an already running GitHub job is not cancelled and may finish afterward.
- A failed edition stays claimed. This intentionally prevents an automatic rerun
  from overwriting audio or double-publishing after an ambiguous response.
- State records are retained indefinitely (small JSON files); no lifecycle cleanup
  silently reopens a previously claimed date. A manual rerun must be reviewed.

Use Google Cloud Console > Workflows > `nba-daily-orchestrator` > Executions for
final success/failure and run URLs; use Scheduler for trigger status. No email or
chat notification channel is created by this deployment.

Recovery is manual: inspect the exact GitHub runs and stored records first.
Do not delete an edition claim or dispatch again until generation/publication
state is understood and the intended retry is authorized. The scheduler chooses
today's Eastern edition and is not a backfill tool.

## Pause and costs

```bash
gcloud scheduler jobs pause nba-daily-1100-madrid --project="$PROJECT_ID" \
  --location="$REGION"
```

Pausing stops future starts, not active executions. A paused Scheduler job still
counts for billing. Expected incremental cost at one daily sequence and minute
polling is near zero (roughly $0–$0.50/month, depending on shared free allowances
and runtime), plus tiny private state Storage usage. Existing GitHub Actions,
Gemini, audio generation, and audio storage charges are separate.

## Local validation

In an isolated Python 3.12 virtual environment:

```bash
pip install -r infrastructure/cloud-scheduler/requirements-test.txt
python infrastructure/cloud-scheduler/test_orchestrator.py -v
bash -n infrastructure/cloud-scheduler/deploy.sh
git diff --check
```

The tests interpret the actual YAML control flow with fake cloud/GitHub calls.
They cover success ordering, frozen Eastern date across the UTC date boundary,
generation failure/cancellation, publisher failure, two-hour timeout, duplicate
claims, active earlier runs, uncertain dispatch, and dry-run side-effect freedom.
They do not replace Google's workflow compiler or a credential preflight.

Pricing: https://cloud.google.com/scheduler/pricing,
https://cloud.google.com/workflows/pricing,
https://cloud.google.com/secret-manager/pricing.
