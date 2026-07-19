# Shared UI domain policy

Shared-block ownership follows
[`CFG-SINGLE-WORKSPACE-OWNER`](../../architecture.md#cfg-single-workspace-owner):
`astro-ui-m8` is the declared owner. Business plugins consume registry blocks
at setup time through `shadcn add`; copied blocks are not runtime imports.

Extend a missing capability in `astro-ui-m8` with tests and a registry rebuild,
then consume it downstream. Do not fork a one-off registry block into a
business plugin. Business plugins depend on `@mano8/astro-ui-m8`, declare any
registry dependencies in their own `registry.json`, and do not own the shared
data-table block.
