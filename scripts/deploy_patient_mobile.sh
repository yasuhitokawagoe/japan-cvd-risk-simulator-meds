#!/usr/bin/env bash
# Deploy only a committed mobile branch, never overwrite either PC service.
set -euo pipefail
mobile_repo=$(git rev-parse --show-toplevel)
cd "$mobile_repo"
if [ "$(git branch --show-current)" != "codex/patient-mobile-preview" ]; then
  printf '%s\n' 'Switch to codex/patient-mobile-preview before deploying.' >&2
  exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  printf '%s\n' 'Commit tracked changes before deploying.' >&2
  exit 1
fi
mobile_revision=$(git rev-parse --short HEAD)
mobile_stage=$(mktemp -d /private/tmp/dm-care-mobile.XXXXXX)
git archive HEAD | tar -x -C "$mobile_stage"
cp "$mobile_stage/railway.mobile.json" "$mobile_stage/railway.json"
printf 'Deploying commit %s from %s\n' "$mobile_revision" "$mobile_stage"
railway up "$mobile_stage" --path-as-root \
  --project 9aff4332-215b-452a-a15d-3311a749b8f4 \
  --service eb150316-9352-41c2-9703-d7f7b161c7e1 \
  --environment cb55a094-a77b-4def-ab04-b656197b619d \
  --detach --json --message "Patient mobile preview $mobile_revision"
