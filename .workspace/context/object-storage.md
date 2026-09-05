# Object-Storage Backend Policy

Canonical owner of the fleet's object-storage backend contract and the ratified
default/fallback pair. Ratified by `T5-ratify-backend` of the
`media-sdk-m8/todo/object-storage-backend-migration-2026-09-05.md` plan
(gitignored; not the authority — this file is), after `T0`–`T4` proved the
candidates against the executable S3 conformance harness in
`media-sdk-m8/tests/conformance/`.

Workspace invariant: [`CFG-SINGLE-WORKSPACE-OWNER`](../architecture.md#cfg-single-workspace-owner)
— this file is the sole canonical owner of the backend decision; no child
repository or agent-specific directory may keep a competing copy of it.

## Ratified policy

```text
Object-storage contract:            Amazon S3 API (SigV4)
Local/LAN reference implementation: SeaweedFS 4.x  (weed server -filer -s3)
Validated alternative:              Garage 2.x
Cloud implementation:               any S3-compatible provider
Application code:                   never depends on a specific implementation
Watchlist (not production):         RustFS — revisit after a stable 1.x series
```

- **Default: SeaweedFS 4.x**, pinned `chrislusf/seaweedfs:4.45` at measurement
  time. Faster patch velocity, Apache-2.0 licence, and a feature ceiling
  (versioning, object lock, bucket policy, IAM) that Garage does not have —
  weighed against a larger default attack surface, closed by
  `-ip.bind=127.0.0.1 -s3.ip.bind=0.0.0.0 -ip=<loopback>`, which binds
  master/volume/filer/webdav to the container's own loopback interface so only
  the S3 port is reachable from any sibling.
- **Validated fallback: Garage 2.x**, pinned `dxflrs/garage:v2.3.0`. AGPLv3,
  slower release cadence, and a coarser per-key-per-bucket permission model
  (Read/Write/Owner only — no distinct delete verb, no bucket policy, no
  object versioning or lock, no IAM) — but genuinely simpler operationally
  (one extra port, RPC, versus SeaweedFS's four) and equally sufficient for
  every S3 operation and every security invariant this fleet's media stack
  exercises.
- **Fallback rule** (unchanged from the plan): if a future SeaweedFS release
  regresses any of S9–S12 in `media-sdk-m8/tests/conformance/`, the default
  switches to Garage without re-planning — the conformance harness is what
  makes that a test run instead of a re-analysis.

## Evidence

`media-sdk-m8/tests/conformance/MATRIX.md` records `pytest -m conformance
--backend=<name>` for all three measured candidates:

| Backend | Image | Surface (`OP-01`–`OP-13`) | Invariants (`S2`, `S4`, `S5`, `S9`–`S12`) |
| --- | --- | --- | --- |
| MinIO (baseline) | `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z.hotfix.7aa24e772` | 13/13 pass | 6/6 pass, `S2` not evaluable (single listener, no separate admin port) |
| SeaweedFS (ratified default) | `chrislusf/seaweedfs:4.45` | 13/13 pass | 7/7 pass |
| Garage (validated fallback) | `dxflrs/garage:v2.3.0` | 13/13 pass | 7/7 pass |

Both candidates pass every row the harness can evaluate against them — the
decision is not a tie-break on missing capability, it is the licence/velocity/
feature-ceiling-versus-attack-surface trade recorded above.

## What does not move

`FORBIDDEN_OPERATIONS` in `media-sdk-m8/tests/conformance/contract.py` still
applies regardless of backend: no bucket policy, no anonymous/public read, no
lifecycle configuration, no versioning, no object lock, no ACLs, no tagging, no
server-side encryption configuration. `public-media` stays served through a
scan-gated presigned GET, never anonymous read.
