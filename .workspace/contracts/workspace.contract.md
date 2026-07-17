# Workspace Contract

## System Invariants

- Platform is reusable only
- Services are isolated domains
- Clients never bypass services
- No service-to-service imports

---

## Enforcement Rule

Any violation is a hard architectural drift condition.

These are not warnings - they are invalid system states.

