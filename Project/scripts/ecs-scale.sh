#!/usr/bin/env bash
# Scale the backend ECS service to pause/resume Fargate cost.
#   ./ecs-scale.sh 0   # pause (no tasks, ~$0 Fargate)
#   ./ecs-scale.sh 1   # resume (1 task, ~$9/mo if left 24/7)
#
# NOTE: the ALB (~$16/mo) is always-on and is NOT paused by this script.
# Scaling to 0 stops only the Fargate task cost; the ALB keeps running.
set -euo pipefail

COUNT="${1:-}"
if [[ "$COUNT" != "0" && "$COUNT" != "1" ]]; then
  echo "Usage: $0 <0|1>   (0 = pause Fargate, 1 = resume)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../.env"

CLUSTER="sps-shared-${TF_VAR_environment}-cluster" # sps-shared-dev-cluster
SERVICE="sps-shared-${TF_VAR_environment}-backend"  # sps-shared-dev-backend

echo "Setting $SERVICE desired-count to $COUNT (cluster $CLUSTER)..."
[[ "$COUNT" == "0" ]] && echo "Reminder: this pauses Fargate only — the ALB keeps billing (~\$16/mo)."

aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --desired-count "$COUNT" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --query 'service.{service:serviceName,desired:desiredCount,running:runningCount}' \
  --output table
