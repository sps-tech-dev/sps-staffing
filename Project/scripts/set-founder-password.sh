#!/usr/bin/env bash
# Set the founder's password OUT-OF-BAND (never in the repo / migration).
#
# Flow (plaintext NEVER leaves this terminal, never hits disk, never logged):
#   1. Prompt for the password twice (hidden), confirm match + strength.
#   2. Hash it LOCALLY with argon2 inside the app image (same scheme the app
#      verifies with) — plaintext is piped to the container via stdin only.
#   3. Run a one-off ECS task in the VPC that UPDATEs shared.users, receiving
#      only the (non-reversible) argon2 HASH via an env override — not plaintext,
#      and the task never prints the hash. RDS creds come from Secrets Manager
#      (same path as the app/migration), so no DB creds here either.
#
# Requires: the app image present locally as sps-backend:dev (for hashing).
set -euo pipefail

EMAIL="sandeep@spstechnosoft.com"
IMAGE="sps-backend:dev"
MIN_LEN=12

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../.env"

# --- 1. hidden prompt x2 ---------------------------------------------------
read -r -s -p "New founder password (min ${MIN_LEN} chars): " PW1; echo
read -r -s -p "Confirm password: " PW2; echo
if [[ "$PW1" != "$PW2" ]]; then echo "ERROR: passwords do not match." >&2; exit 1; fi

# --- 2. basic strength gate ------------------------------------------------
if (( ${#PW1} < MIN_LEN )); then echo "ERROR: too short (min ${MIN_LEN})." >&2; exit 1; fi
shopt -s nocasematch
if [[ "$PW1" =~ ^(password|passw0rd|12345678|qwerty|letmein|admin|welcome|sps|spstechnosoft) ]] \
   || [[ "$PW1" =~ ^(.)\1+$ ]]; then
  echo "ERROR: password is too weak / predictable." >&2; exit 1
fi
shopt -u nocasematch

# --- 3. hash LOCALLY in the app image (plaintext via stdin only) -----------
HASH="$(printf '%s' "$PW1" | docker run -i --rm "$IMAGE" \
  python -c 'import sys,argon2; print(argon2.PasswordHasher().hash(sys.stdin.read()), end="")')"
unset PW1 PW2
if [[ -z "$HASH" || "$HASH" != \$argon2* ]]; then
  echo "ERROR: hashing failed (is $IMAGE built locally?)." >&2; exit 1
fi
echo "Password hashed locally (argon2). Applying via one-off ECS task..."

# --- 4. UPDATE via one-off ECS task in the VPC -----------------------------
SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=sps-shared-${TF_VAR_environment}-ecs-sg" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' --output text)
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=sps-shared-${TF_VAR_environment}-private-app-*" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'Subnets[].SubnetId' --output text | tr '\t' ',')

# The hash is passed via an ENV override (not the command, not logged). The
# UPDATE uses a parameterized query so the hash is never interpolated into SQL.
UPDATE_PY='import os,psycopg
h=os.environ["FOUNDER_PW_HASH"]
c=psycopg.connect(host=os.environ["DB_HOST"],port=os.environ["DB_PORT"],dbname=os.environ["DB_NAME"],user=os.environ["DB_USER"],password=os.environ["DB_PASSWORD"])
cur=c.cursor()
cur.execute("UPDATE shared.users SET password_hash=%s, status=%s WHERE email=%s AND tenant_id=(SELECT id FROM shared.tenants WHERE code=%s)",(h,"active",os.environ["FOUNDER_EMAIL"],"SPS001"))
c.commit()
print("ROWS_UPDATED="+str(cur.rowcount))'

# Serialize the run-task overrides with a real JSON serializer (json.dumps) so
# all quoting/newlines are correct regardless of the script's contents — no
# fragile string concatenation. The hash + email + script are passed to the
# serializer via env, never as args. Output goes to a 0600 temp file (it holds
# the non-reversible HASH, not plaintext) that is removed on exit; the hash is
# never echoed and reaches the ECS task only via the env override.
OVERRIDES_FILE="$(mktemp)"
chmod 600 "$OVERRIDES_FILE"
trap 'rm -f "$OVERRIDES_FILE"' EXIT

H="$HASH" EMAIL="$EMAIL" SCRIPT="$UPDATE_PY" docker run -i --rm -e H -e EMAIL -e SCRIPT "$IMAGE" \
  python -c 'import json,os,sys; sys.stdout.write(json.dumps({"containerOverrides":[{"name":"migrate","command":["python","-c",os.environ["SCRIPT"]],"environment":[{"name":"FOUNDER_PW_HASH","value":os.environ["H"]},{"name":"FOUNDER_EMAIL","value":os.environ["EMAIL"]}]}]}))' \
  > "$OVERRIDES_FILE"
unset HASH

if ! grep -q FOUNDER_PW_HASH "$OVERRIDES_FILE"; then echo "ERROR: failed to build overrides JSON." >&2; exit 1; fi

TASK_ARN=$(aws ecs run-task --cluster "sps-shared-${TF_VAR_environment}-cluster" \
  --task-definition "sps-shared-${TF_VAR_environment}-migrate" --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG],assignPublicIp=DISABLED}" \
  --overrides "file://$OVERRIDES_FILE" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --query 'tasks[0].taskArn' --output text)
echo "Task: $TASK_ARN — waiting..."
aws ecs wait tasks-stopped --cluster "sps-shared-${TF_VAR_environment}-cluster" --tasks "$TASK_ARN" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION"
EXIT=$(aws ecs describe-tasks --cluster "sps-shared-${TF_VAR_environment}-cluster" --tasks "$TASK_ARN" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --query 'tasks[0].containers[0].exitCode' --output text)
TASK_ID="${TASK_ARN##*/}"
echo "=== task log (should show ROWS_UPDATED=1; no hash printed) ==="
aws logs get-log-events --log-group-name "/ecs/sps-shared-${TF_VAR_environment}-migrate" \
  --log-stream-name "migrate/migrate/$TASK_ID" \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" --query 'events[*].message' --output text 2>/dev/null || true
echo "exitCode=$EXIT"
[[ "$EXIT" == "0" ]] && echo "FOUNDER PASSWORD SET (status -> active)" || { echo "FAILED"; exit 1; }
