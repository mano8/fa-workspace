# Cross-repository task

Cross-repository work requires a canonical explicit repository set and a
recorded human authorization whose repository and operation scopes match it
exactly. A child's instructions have authority only under that child's
registered prefix and cannot authorize work in a sibling.

Preserve the dependency and data boundaries in
[`ARCH-LAYER-DIRECTION`](../../architecture.md#arch-layer-direction) and
[`ARCH-NO-CROSS-SERVICE-DATA`](../../architecture.md#arch-no-cross-service-data).
Use owned contracts or HTTP APIs across services; do not create source imports,
private-data access, or shared runtime configuration between children.
