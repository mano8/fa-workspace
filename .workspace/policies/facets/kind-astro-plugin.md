# Astro-plugin policy

An Astro plugin is a business integration and headless client package. It
fronts its service through the HTTP contract, has a package shape independent
of the host, and never imports another optional plugin or forms dependency
cycles.

It supports `headless` (schemas, clients, adapters, and hooks without injected
pages), `starter` (default `.astro` routes), and `scaffolded`
(consumer-owned views) modes. Every business plugin supports both full/starter
routes and headless composition, provides a configurable `basePath`, avoids
route-path collisions, lets the host own navigation in headless mode, and
fails fast with a clear error if its required auth adapter is missing.
