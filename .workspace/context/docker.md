# Docker Infrastructure Policy

## Stack
- Docker Compose
- Traefik
- Redis / MySQL or Postgres / MinIO

## Rules
- all secrets via env or vault only
- no hardcoded credentials
- persistent volumes required

## Deployment Rules
- migrations must run before service startup
- no partial initialization states allowed

