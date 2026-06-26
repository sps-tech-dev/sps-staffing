#!/usr/bin/env bash
# Stop the dev RDS instance to save cost (~$25/mo running → ~$3/mo stopped, storage only).
# NOTE: AWS automatically restarts a stopped RDS instance after 7 days.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../.env"

DB_INSTANCE_ID="sps-shared-${TF_VAR_environment}-rds" # sps-shared-dev-rds (canonical shared-layer name)

echo "Stopping RDS instance: $DB_INSTANCE_ID"
echo "Reminder: AWS auto-restarts a stopped RDS instance after 7 days."

aws rds stop-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION"
