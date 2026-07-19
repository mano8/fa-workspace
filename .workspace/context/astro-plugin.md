# Astro plugin core policy

This compatibility source retains only the stable architecture shared by the
M8 business Astro integrations. Active faceted resolution uses the equivalent
kind, framework, layer, and domain policy units; the retained W3 selector is
rollback metadata only.

## Core invariants

- A business plugin is a self-contained Astro integration and headless client
  package. It fronts exactly one backend through its HTTP contract and never
  imports service source, contains a host, imports another optional plugin, or
  forms a dependency cycle.
- Each plugin supports `headless`, `starter`, and `scaffolded` modes. It
  provides both production-ready starter routes and headless composition,
  exposes a configurable `basePath`, avoids route collisions, leaves navigation
  to the host in headless mode, and fails fast when its required adapter is
  unavailable.
- The plugin remains portable and usable without this workspace checkout. Its
  public API, internal layout, package metadata, exact scripts, coverage gate,
  service-specific contract metadata, and shared-UI registry inventory remain
  child-owned or discoverable facts.

Registry/scaffolding, host wiring, auth-adapter integration, package testing,
and release procedures are opt-in tasks. Select the matching task policy only
for that operation; this core does not prescribe those procedures.
