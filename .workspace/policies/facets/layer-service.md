# Service-layer policy

- A service never imports another service directly; cross-service access uses
  an owned contract or HTTP API only
  ([`ARCH-LAYER-DIRECTION`](../../architecture.md#arch-layer-direction)).
- A service owns only its own schema and storage; it never reads or writes
  another service's data directly
  ([`ARCH-NO-CROSS-SERVICE-DATA`](../../architecture.md#arch-no-cross-service-data)).
- A service fails fast when its required environment configuration is
  incomplete rather than starting in a partially configured state.
