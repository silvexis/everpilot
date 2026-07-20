# Everpilot infrastructure

CloudFormation, following the patterns in
[CloudZero/cz-standards](https://github.com/Cloudzero/cz-standards) while
remaining **account-agnostic** — Everpilot is a Silvexis product, so nothing
here hardcodes CloudZero account ids, shared-VPC secret ARNs, or corp domains.

## Stacks (deploy order)

| Stack | Template | Purpose |
|---|---|---|
| `cz-{ns}-everpilot-network` | `network.yaml` | VPC, 2×public + 2×private subnets, 1 NAT, S3 gateway endpoint. Optional — `SKIP_NETWORK=1` + `VPC_ID`/`*_SUBNETS` env when the account provides shared networking |
| `cz-{ns}-everpilot-ecr` | `ecr.yaml` | Immutable-tag ECR repo, scan-on-push, keep-20 lifecycle |
| `cz-{ns}-everpilot` | `app.yaml` | ECS Fargate service (API + in-process DBOS workers), internet-facing ALB, RDS Postgres 17, CloudWatch alarm |
| `github-oidc-everpilot` | `github-oidc-role.yaml` | One-time OIDC deploy role (main-branch-scoped; no static keys). Deploy it with the 11 `--tags` too: `aws cloudformation deploy --stack-name github-oidc-everpilot --template-file infra/github-oidc-role.yaml --capabilities CAPABILITY_NAMED_IAM --tags cz:feature=everpilot ...` |

`./scripts/deploy.sh <alfa|live>` runs the whole sequence: SSM prerequisite
validation (`ssm-prereqs.conf`) → stacks → image build/push (immutable git-sha
tags) → app deploy, with the 11 required tags applied **stack-level**.

## Standards conformance

- **Tags**: all 11 `cz:*`/`aws-apn-id` tags via `--tags` (govern-tagging-policy).
- **Naming**: `cz-{namespace}-{feature}` stacks; `live`→prod, `alfa`→stage.
- **Secrets**: SSM SecureString under `/cz/everpilot/{namespace}/{key}`; task
  role scoped to `parameter/cz/everpilot/*` with `aws:SecureTransport`; RDS
  password via `{{resolve:ssm-secure:...}}`. The container receives only
  non-secret wiring (`EVERPILOT_SSM_CONFIG`, `CZ_FEATURE`, `CZ_NAMESPACE`,
  `DB_HOST`); secrets load through a pydantic-settings SSM source
  (`config.py:SsmParameterSource`) straight into the Settings object — never
  into `os.environ`, so child processes don't inherit them. `DATABASE_URL` is
  composed from `DB_HOST` + the SSM password, not stored as a parameter.
- **Migrations**: `docker-entrypoint.sh` runs `alembic upgrade head` in-VPC
  before uvicorn — the only path that can reach the private-subnet RDS.
- **Networking**: service and database in private subnets only; DB ingress only
  from the service SG; service ingress only from the ALB SG.
- **CI/CD**: `cfn-lint` on every PR; deploys via OIDC role, main branch only.

## Documented deviations

1. **Own VPC** (`network.yaml`): the "never create your own VPC" rule assumes
   CloudZero's cz-prime shared networking, which doesn't exist outside those
   accounts. Deploying into a CloudZero account? Use `SKIP_NETWORK=1` and the
   Schema B secret references instead.
2. **ECS Fargate over container Lambda**: DBOS Transact runs durable workflows
   in a long-lived process; Lambda's execution model can't host it. The
   `ecs-lambda-workload` subnet purpose in the standards acknowledges ECS.
3. **ALB is internet-facing**: GitHub webhooks must reach the API. Ingress is
   TLS-terminated at the ALB; webhook payloads are HMAC-verified in-app.

## Cost notes

- **NAT gateway** (~$33/mo/namespace) is the biggest idle line item and exists
  only for the task's outbound calls (GitHub, Anthropic, ECR, logs). Kept for
  the standards-conformant private-subnet posture, but for a cost-sensitive V1
  a fck-nat micro-instance (~$3/mo) or running the single task in public
  subnets (SG still ALB-only) are documented cheaper swaps — see
  docs/open_questions.md.
- Container Insights is left **off** (per-task metrics aren't worth ~$5-11/mo on
  a one-task cluster); the free ECS/ALB metrics plus the 5xx alarm suffice.
- ECR repos are per-namespace so alfa's image churn can't expire live's pinned
  image.

## Open decisions (docs/open_questions.md)

Which AWS account/org this deploys into, the domain names, and the NAT cost
tradeoff. Templates are parameterized so none block authoring or linting.
