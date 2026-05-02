# Deployment and Industrial Operations Research

Access date: 2026-05-01

## 1) Research Question
How should FactoryMind AgentOS run reliably in local development, single-server deployments, and AWS/self-hosted production environments?

This block defines deployment topology, operational services, scaling, secrets, backups, monitoring, and SLOs.

## 2) Short Answer
FactoryMind AgentOS should support two deployment paths:

```text
Local / single-server:
  Docker Compose
  Postgres + pgvector
  Redis
  FactoryMind AgentOS API + worker

Production:
  AWS ECS/Fargate
  RDS Postgres + pgvector
  ElastiCache Redis
  SQS or Redis/RabbitMQ queue
  Secrets Manager + KMS
  OpenTelemetry collector
  CloudWatch/OTLP backend
```

V1 should not require Kubernetes. Kubernetes can be supported later for larger deployments.

## 3) Runtime Components
| Component | Purpose | Local | Production |
|---|---|---|---|
| API service | Session API, CLI service mode, control endpoints | Docker service | ECS/Fargate service |
| Worker service | Runtime execution, learning jobs, eval jobs | Docker service | ECS/Fargate service |
| Scheduler | Periodic learning/eval/replay jobs | worker beat/simple cron | EventBridge or worker scheduler |
| Postgres | sessions, audit, memory, skills, candidates | container | RDS PostgreSQL |
| pgvector | memory/skill embeddings | Postgres extension | RDS-compatible extension if available |
| Redis | session cache, queues, locks | container | ElastiCache |
| Object store | large artifacts, redacted payload refs | local filesystem/minio | S3 |
| Trace collector | OTLP traces/metrics/logs | optional container | OpenTelemetry Collector |
| Secrets | provider/API/database secrets | `.env` local only | Secrets Manager + KMS |

## 4) Local Development Deployment
Recommended local stack:

```text
docker compose up
  api
  worker
  postgres
  redis
  otel-collector optional
```

Local goals:
- fast setup
- realistic enough to test sessions, memory, skills, evals, and audit
- no managed cloud dependency
- no production secrets

Docker Compose profiles:
- `default`: API, worker, Postgres, Redis
- `observability`: OTEL collector, trace viewer
- `devtools`: admin/debug tools
- `eval`: eval worker and test datasets

## 5) Production Deployment Recommendation
Recommended first production path:
- AWS ECS/Fargate instead of EKS
- RDS PostgreSQL
- ElastiCache Redis
- S3 artifact storage
- Secrets Manager
- KMS encryption
- CloudWatch + OTLP-compatible tracing backend

Why ECS/Fargate first:
- lower operational burden than Kubernetes
- good fit for one engineer
- managed scaling
- private VPC support
- no cluster/node management

Use Kubernetes later only if:
- customer already runs Kubernetes
- multi-tenant scale requires custom scheduling
- Temporal/Kafka/operators become necessary

## 6) Service Boundaries
Split services:

```text
agent-os-api
agent-os-worker
agent-os-scheduler
agent-os-eval-worker
agent-os-learning-worker
```

V1 can combine worker types into one process locally, but production should allow them to scale independently.

Reason:
- API needs low latency.
- Eval/learning jobs are batchy and expensive.
- Runtime sessions may need different concurrency than evals.
- Tool/MCP calls may need separate rate limits.

## 7) Queue Strategy
V1 options:

| Queue | Fit | Recommendation |
|---|---|---|
| Redis queue / Celery | Simple local + production path | Good v1 default |
| SQS | AWS-native, managed durability | Strong production option |
| RabbitMQ | Mature broker, more ops | Useful later |
| Temporal | Durable workflows | Phase 2 for long-running jobs |

Recommended:
- local: Redis-backed queue
- production v1: SQS or Redis-backed Celery depending simplicity
- phase 2: Temporal for reflection/promotion workflows if long-running reliability becomes critical

## 8) State and Storage
Postgres should own durable state:
- agents
- sessions
- messages
- checkpoints metadata
- audit events
- memories
- skills
- candidates
- eval runs
- approvals
- rollbacks

Redis should own ephemeral state:
- locks
- short-lived session cache
- queue state if using Redis queue
- rate limit counters

S3/object store should own:
- large trace payloads
- redacted artifacts
- eval reports
- accepted output files
- incident bundles

## 9) Secrets and Encryption
Production rules:
- no secrets in `.env` files on servers
- use AWS Secrets Manager
- encrypt secrets with KMS
- use IAM roles for ECS tasks
- use private networking and VPC endpoints where practical
- rotate provider/API/database credentials
- avoid logging secrets or raw prompts containing secrets

Local rules:
- `.env` allowed for development
- `.env` must be gitignored
- local test secrets must be non-production

## 10) Network and Isolation
Production network baseline:
- private subnets for API/worker if exposed through internal load balancer
- RDS and Redis private only
- restricted outbound egress
- security groups per service
- no public database endpoints
- TLS for external and internal service calls where practical

MCP server rule:
- internal MCP servers should run inside the same private network.
- third-party MCP servers require explicit approval and network allowlist.

## 11) Scaling Model
Scale independently:
- API by request rate
- runtime workers by active sessions
- eval workers by queued eval jobs
- learning workers by candidate generation queue
- MCP gateway by tool call rate

Key metrics:
- API request latency
- active sessions
- queue depth
- worker error rate
- model call latency
- tool call latency
- eval job duration
- learning candidate throughput
- rollback count

## 12) Reliability Targets
Suggested v1 SLOs:

| Area | Target |
|---|---|
| API availability | 99.5% during business hours |
| Session checkpoint success | >= 99.0% |
| Tool call audit coverage | 100% |
| Skill/memory promotion audit coverage | 100% |
| Recovery from worker crash | resume from checkpoint |
| Rollback time for learned change | <= 15 minutes |
| Data backup RPO | <= 24 hours v1 |
| Data recovery RTO | <= 4 hours v1 |

For early prototypes, document lower SLOs explicitly.

## 13) Backup and Disaster Recovery
Required:
- automated Postgres backups
- periodic restore tests
- S3 versioning for artifacts
- audit event retention policy
- exported config snapshots
- rollback registry backups

Restore test should verify:
- sessions can be read
- memory/skills can be restored
- audit chain remains valid
- promoted skill versions and rollback targets survive restore

## 14) Deployment Phases
### Phase 1: Local Package Runtime
- `agent-os init`
- Docker Compose local stack
- Postgres + Redis
- API + worker
- local traces/logs

### Phase 2: Single-Server / Small Team
- Docker Compose production profile
- remote Postgres or local managed Postgres
- TLS reverse proxy
- backups
- basic monitoring

### Phase 3: AWS Production
- ECS/Fargate
- RDS PostgreSQL
- ElastiCache Redis
- S3 artifacts
- Secrets Manager
- KMS
- CloudWatch + OTEL collector

### Phase 4: Enterprise / High Scale
- Kubernetes or ECS service split
- Temporal workflows
- multi-region backups
- tenant isolation
- SIEM integration
- external policy engine

## 15) Operational Runbooks
FactoryMind AgentOS should ship runbooks for:
- MCP server outage
- model provider outage
- queue backlog growth
- bad skill promotion rollback
- memory poisoning response
- database restore
- secret rotation
- audit export
- eval failure investigation

## 16) Build-vs-Wrap Decision
Build:
- Docker Compose reference
- ECS reference architecture
- health checks
- runbooks
- config schema
- backup/restore checklist
- SLO definitions

Wrap:
- AWS ECS/Fargate
- RDS
- ElastiCache
- S3
- Secrets Manager
- KMS
- OpenTelemetry Collector
- Celery/SQS/Temporal later

Do not build:
- custom container orchestrator
- custom secrets manager
- custom database
- custom queue broker

## 17) Final Recommendation
For FactoryMind AgentOS v1:
- Docker Compose for local development and single-server validation
- AWS ECS/Fargate as first production reference
- Postgres + pgvector as durable state
- Redis as cache/queue for v1
- S3 for artifacts
- Secrets Manager + KMS in production
- OpenTelemetry collector for traces

Do not start with Kubernetes unless a customer environment requires it.

## 18) Sources
- AWS Well-Architected Reliability Pillar: https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html
- AWS Well-Architected Framework reliability: https://docs.aws.amazon.com/wellarchitected/2022-03-31/framework/reliability.html
- AWS ECS best practices: https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/application.html
- AWS ECS container image best practices: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-considerations.html
- AWS ECS documentation: https://aws.amazon.com/documentation-overview/ecs/
- AWS Secrets Manager best practices: https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html
- RDS encryption best practices: https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/rds.html
- RDS encryption overview: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.Encryption.html
- Docker Compose production guide: https://docs.docker.com/compose/how-tos/production/
- Docker Compose profiles: https://docs.docker.com/compose/how-tos/profiles/
- Docker Compose reference: https://docs.docker.com/compose/reference/
- Temporal documentation: https://docs.temporal.io/
- Temporal worker versioning/autoscaling update: https://temporal.io/change-log/worker-versioning-continue-as-new-worker-controller
- Celery documentation: https://docs.celeryq.dev/

Research inference:
- The fastest reliable path is not a large platform deployment first. It is a package-first system with local Compose, then ECS/Fargate production reference once the core contracts stabilize.

