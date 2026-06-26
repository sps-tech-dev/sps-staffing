#!/usr/bin/env bash
# Start the dev RDS instance after it has been stopped for cost savings.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../.env"

DB_INSTANCE_ID="sps-shared-${TF_VAR_environment}-rds" # sps-shared-dev-rds (canonical shared-layer name)

echo "Starting RDS instance: $DB_INSTANCE_ID"

aws rds start-db-instance \
  --db-instance-identifier "$DB_INSTANCE_ID" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION"
