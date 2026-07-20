#!/usr/bin/env bash
# Everpilot deploy: ./scripts/deploy.sh <alfa|live> [--account-id <id>]
#
# Follows cz-standards cicd-internal-apps conventions:
# - stack names cz-{namespace}-{feature}
# - the 11 required tags applied STACK-LEVEL via --tags (never per-resource)
# - SSM prerequisites validated before any stack deploy (infra/ssm-prereqs.conf)
# - fails fast on account mismatch and on a dirty working tree
#
# CI note: run the deploy job on an ARM64 runner (ubuntu-24.04-arm) so the
# linux/arm64 image builds natively instead of ~10x slower under QEMU.
set -euo pipefail

FEATURE="everpilot"
REGION="${AWS_REGION:-us-east-1}"
NAMESPACE="${1:-}"
[[ "$NAMESPACE" == "alfa" || "$NAMESPACE" == "live" ]] || {
  echo "usage: $0 <alfa|live> [--account-id <id>]" >&2
  exit 1
}
shift
EXPECTED_ACCOUNT=""
[[ "${1:-}" == "--account-id" ]] && EXPECTED_ACCOUNT="${2:?--account-id needs a value}"

ENV_TAG=$([[ "$NAMESPACE" == "live" ]] && echo "prod" || echo "stage")
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [[ -n "$EXPECTED_ACCOUNT" && "$ACCOUNT_ID" != "$EXPECTED_ACCOUNT" ]]; then
  echo "FATAL: authenticated to account $ACCOUNT_ID, expected $EXPECTED_ACCOUNT" >&2
  exit 1
fi

# Immutable image tags must match a clean commit (ECR forbids overwrite, so a
# dirty build would pin non-reproducible contents to a sha forever).
if [[ -n "$(git status --porcelain)" ]]; then
  echo "FATAL: working tree is dirty; commit or stash before deploying" >&2
  exit 1
fi
IMAGE_TAG=$(git rev-parse --short=12 HEAD)

# --- The 11 required tags (govern-tagging-policy), stack-level ---
TAGS=(
  "cz:feature=${FEATURE}"
  "cz:owner=erik@cloudzero.com"
  "cz:team=erik@cloudzero.com"
  "cz:env=${ENV_TAG}"
  "cz:namespace=${NAMESPACE}"
  "cz:customer-data=true"
  "cz:customer-data-description=customer repository metadata and task history"
  "cz:access=customer"
  "cz:description=autonomous code maintenance saas"
  "cz:repo=silvexis/everpilot"
  "aws-apn-id=pc:235i70hhsejh3lbwywcc2rwqn"
)

stack_output() {
  aws cloudformation describe-stacks --stack-name "$1" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text
}

deploy_stack() {
  local stack="$1" template="$2"
  shift 2
  echo "Deploying $stack ..."
  aws cloudformation deploy \
    --stack-name "$stack" \
    --template-file "$template" \
    --region "$REGION" \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset \
    --tags "${TAGS[@]}" \
    "$@"
}

# --- SSM prerequisite validation (infra/ssm-prereqs.conf), batched ---
echo "Validating SSM prerequisites under /cz/${FEATURE}/${NAMESPACE}/ ..."
declare -A REQUIRED_DESC
NAMES=()
while IFS='|' read -r key type required _default description; do
  [[ -z "$key" || "$key" == \#* ]] && continue
  path="/cz/${FEATURE}/${NAMESPACE}/${key}"
  NAMES+=("$path")
  [[ "$required" == "true" ]] && REQUIRED_DESC["$path"]="$type|$description"
done <infra/ssm-prereqs.conf

# One batched lookup (get-parameters accepts up to 10 names)
FOUND=$(aws ssm get-parameters --names "${NAMES[@]}" --region "$REGION" \
  --query "Parameters[].Name" --output text 2>/dev/null || true)
MISSING_REQUIRED=0
for path in "${!REQUIRED_DESC[@]}"; do
  if ! grep -qw "$path" <<<"$FOUND"; then
    IFS='|' read -r ptype pdesc <<<"${REQUIRED_DESC[$path]}"
    echo "MISSING (required): $path — $pdesc" >&2
    echo "  remediation: aws ssm put-parameter --name '$path' --type $ptype --value '...'" >&2
    MISSING_REQUIRED=1
  fi
done
[[ "$MISSING_REQUIRED" -eq 0 ]] || exit 1

# 1. Network (skip with SKIP_NETWORK=1 when the account provides shared networking)
NETWORK_STACK="cz-${NAMESPACE}-${FEATURE}-network"
if [[ "${SKIP_NETWORK:-0}" != "1" ]]; then
  deploy_stack "$NETWORK_STACK" infra/network.yaml --parameter-overrides "FeatureName=${FEATURE}"
  VPC_ID=$(stack_output "$NETWORK_STACK" VpcId)
  PUBLIC_SUBNETS=$(stack_output "$NETWORK_STACK" PublicSubnetIds)
  PRIVATE_SUBNETS=$(stack_output "$NETWORK_STACK" PrivateSubnetIds)
else
  : "${VPC_ID:?SKIP_NETWORK=1 requires VPC_ID}"
  : "${PUBLIC_SUBNETS:?SKIP_NETWORK=1 requires PUBLIC_SUBNETS}"
  : "${PRIVATE_SUBNETS:?SKIP_NETWORK=1 requires PRIVATE_SUBNETS}"
fi

# 2. ECR (per-namespace repo)
ECR_STACK="cz-${NAMESPACE}-${FEATURE}-ecr"
deploy_stack "$ECR_STACK" infra/ecr.yaml \
  --parameter-overrides "FeatureName=${FEATURE}" "Namespace=${NAMESPACE}"
REPO_URI=$(stack_output "$ECR_STACK" RepositoryUri)
REPO_NAME="${REPO_URI##*/}"

# 3. Build & push (immutable tag = git sha; skip if already present)
IMAGE_URI="${REPO_URI}:${IMAGE_TAG}"
if ! aws ecr describe-images --repository-name "$REPO_NAME" \
  --image-ids "imageTag=${IMAGE_TAG}" --region "$REGION" >/dev/null 2>&1; then
  echo "Building and pushing ${IMAGE_URI} ..."
  aws ecr get-login-password --region "$REGION" |
    docker login --username AWS --password-stdin "${REPO_URI%%/*}"
  docker build --platform linux/arm64 -t "$IMAGE_URI" backend/
  docker push "$IMAGE_URI"
fi

# 4. Application
APP_STACK="cz-${NAMESPACE}-${FEATURE}"
deploy_stack "$APP_STACK" infra/app.yaml \
  --parameter-overrides \
  "FeatureName=${FEATURE}" \
  "Namespace=${NAMESPACE}" \
  "VpcId=${VPC_ID}" \
  "PublicSubnetIds=${PUBLIC_SUBNETS}" \
  "PrivateSubnetIds=${PRIVATE_SUBNETS}" \
  "ImageUri=${IMAGE_URI}" \
  "CertificateArn=${CERTIFICATE_ARN:-}" \
  "AlarmTopicArn=${ALARM_TOPIC_ARN:-}"

aws cloudformation describe-stacks --stack-name "$APP_STACK" \
  --region "$REGION" --query "Stacks[0].Outputs" --output table
echo "Done. Point the GitHub App webhook at https://<domain>/api/v1/webhooks/github"
