#!/usr/bin/env bash
# Run with PROJECT_ID set. Creates a PAUSED job; activation is a separate step.
set -euo pipefail
: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project}"
REGION="${REGION:-europe-west1}"
WORKFLOW=nba-daily-orchestrator
JOB=nba-daily-1100-madrid
SECRET=nba-github-actions-token
STATE_BUCKET="${PROJECT_ID}-nba-orchestration-state"
RUNNER="nba-orchestrator@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER="nba-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
cloud() { gcloud --project="$PROJECT_ID" --quiet "$@"; }

cloud services enable workflows.googleapis.com workflowexecutions.googleapis.com \
  cloudscheduler.googleapis.com secretmanager.googleapis.com
cloud beta services identity create --service=workflows.googleapis.com >/dev/null

for identity in nba-orchestrator nba-scheduler; do
  if ! cloud iam service-accounts describe "${identity}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    cloud iam service-accounts create "$identity" --display-name="$identity"
  fi
done

if ! cloud secrets describe "$SECRET" >/dev/null 2>&1; then
  cloud secrets create "$SECRET" --replication-policy=automatic
fi
cloud secrets add-iam-policy-binding "$SECRET" \
  --member="serviceAccount:$RUNNER" --role=roles/secretmanager.secretAccessor >/dev/null

if ! cloud storage buckets describe "gs://$STATE_BUCKET" >/dev/null 2>&1; then
  cloud storage buckets create "gs://$STATE_BUCKET" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
fi
# Create-only state: the runner cannot erase daily claims or change past run records.
cloud storage buckets add-iam-policy-binding "gs://$STATE_BUCKET" \
  --member="serviceAccount:$RUNNER" --role=roles/storage.objectCreator >/dev/null

cloud workflows deploy "$WORKFLOW" --location="$REGION" \
  --source="$SOURCE_DIR/orchestrator.yaml" --service-account="$RUNNER" \
  --call-log-level=log-none --execution-history-level=execution-history-basic \
  --set-env-vars="STATE_BUCKET=$STATE_BUCKET,GITHUB_SECRET=$SECRET" --format='value(name)'
# Workflows IAM grants are project-scoped. Require separate authorization for
# the narrowly defined start-only role; never grant the broad Invoker role.
if [ "${AUTHORIZE_PROJECT_START_ROLE:-false}" = true ]; then
  if ! cloud iam roles describe nbaWorkflowStarter >/dev/null 2>&1; then
    cloud iam roles create nbaWorkflowStarter --title='NBA workflow starter' \
      --permissions=workflows.executions.create --stage=GA
  fi
  test "$(cloud iam roles describe nbaWorkflowStarter --format='value(includedPermissions)')" = workflows.executions.create
  cloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SCHEDULER" \
    --role="projects/${PROJECT_ID}/roles/nbaWorkflowStarter" >/dev/null
else
  printf '%s\n' 'Project-level start-only IAM grant skipped; explicit authorization required before activation.'
fi

URI="https://workflowexecutions.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/workflows/${WORKFLOW}/executions"
# Create with dry_run=true, then pause before installing the live execution body.
# Even if deployment crosses 11:00, initial creation cannot dispatch GitHub runs.
if cloud scheduler jobs describe "$JOB" --location="$REGION" >/dev/null 2>&1; then
  cloud scheduler jobs pause "$JOB" --location="$REGION"
  cloud scheduler jobs update http "$JOB" --location="$REGION" \
    --schedule='0 11 * * *' --time-zone=Europe/Madrid --uri="$URI" \
    --http-method=POST --oauth-service-account-email="$SCHEDULER" \
    --oauth-token-scope=https://www.googleapis.com/auth/cloud-platform \
    --message-body='{"argument":"{}","callLogLevel":"LOG_NONE"}' \
    --update-headers=Content-Type=application/json --max-retry-attempts=0
else
  cloud scheduler jobs create http "$JOB" --location="$REGION" \
    --schedule='0 11 * * *' --time-zone=Europe/Madrid --uri="$URI" \
    --http-method=POST --oauth-service-account-email="$SCHEDULER" \
    --oauth-token-scope=https://www.googleapis.com/auth/cloud-platform \
    --message-body='{"argument":"{\"dry_run\":true}","callLogLevel":"LOG_NONE"}' \
    --headers=Content-Type=application/json --max-retry-attempts=0
  cloud scheduler jobs pause "$JOB" --location="$REGION"
  cloud scheduler jobs update http "$JOB" --location="$REGION" \
    --message-body='{"argument":"{}","callLogLevel":"LOG_NONE"}'
fi
printf '%s\n' 'Deployed. Schedule remains PAUSED until a dedicated GitHub token is stored and preflight passes.'
