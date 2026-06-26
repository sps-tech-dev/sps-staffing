#!/usr/bin/env bash
# Run the DB migration task ONCE (alembic upgrade head) and report exit + logs.
# Launches the sps-shared-dev-migrate task def in the private-app subnets with
# the ecs SG, no public IP. This is the ONLY way migrations run — never at boot.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../.env"

CLUSTER="sps-shared-${TF_VAR_environment}-cluster"
TASKDEF="sps-shared-${TF_VAR_environment}-migrate"
LOG_GROUP="/ecs/sps-shared-${TF_VAR_environment}-migrate"

# Resolve network config from AWS by name (no jq / no TF state needed).
SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=sps-shared-${TF_VAR_environment}-ecs-sg" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' --output text)
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=sps-shared-${TF_VAR_environment}-private-app-*" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'Subnets[].SubnetId' --output text | tr '\t' ',')

echo "Cluster=$CLUSTER  TaskDef=$TASKDEF"
echo "Subnets=$SUBNETS  SG=$SG"

TASK_ARN=$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASKDEF" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG],assignPublicIp=DISABLED}" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'tasks[0].taskArn' --output text)
echo "Started task: $TASK_ARN"

echo "Waiting for task to stop..."
aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION"

EXIT_CODE=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'tasks[0].containers[0].exitCode' --output text)
REASON=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK_ARN" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'tasks[0].stoppedReason' --output text)

TASK_ID="${TASK_ARN##*/}"
echo "=== migration logs ==="
aws logs get-log-events \
  --log-group-name "$LOG_GROUP" \
  --log-stream-name "migrate/migrate/$TASK_ID" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'events[*].message' --output text 2>/dev/null || echo "(logs not yet available)"

echo "=== result ==="
echo "exitCode=$EXIT_CODE  stoppedReason=$REASON"
[ "$EXIT_CODE" = "0" ] && echo "MIGRATION SUCCEEDED" || { echo "MIGRATION FAILED"; exit 1; }
