# Docker Infrastructure Policy

## Stack
- Docker Compose
- Traefik
- Redis / MySQL or Postgres / MinIO

## Rules
- Workspace invariant:
  [`SEC-NO-TRACKED-SECRETS`](../architecture.md#sec-no-tracked-secrets).
- persistent volumes required

## Deployment Rules
- migrations must run before service startup
- no partial initialization states allowed
