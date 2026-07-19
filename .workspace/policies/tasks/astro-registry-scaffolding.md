# Astro registry and scaffolding task

Use this overlay while choosing or changing an Astro plugin's UI delivery.
Components and hooks may be published through explicit package export subpaths;
when the plugin ships a shadcn registry, keep its source manifest, built
artifacts, and package `files` entries consistent. Registry skins stay pure
shadcn/Tailwind and reuse the plugin's public hooks and React exports instead
of reimplementing live logic.

Shared UI blocks are copied into a consumer at setup time, never runtime
imported from `astro-ui-m8`. Extend a missing shared capability in
`astro-ui-m8`, with its tests, registry rebuild, and documentation, then
consume it downstream. Business plugins declare `@mano8/astro-ui-m8` as a
runtime dependency and declare required registry dependencies in their own
registry metadata; they do not own the shared data-table block.
