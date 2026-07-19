# Astro host-integration task

Use this overlay only while mounting a selected plugin in an Astro/Starlight
host. Enable it only when its package is installed and its `PUBLIC_*_API_BASE`
is configured. Keep integration points small, stable, and clearly marked; do
not copy plugin logic into the host.

- Detect an optional package with `require.resolve` and use a dynamic `import()`
  so an auth-only build does not require it.
- Register the declared Starlight navigation and let `starter` mode inject its
  routes. Supply env defines and, where a headless module is statically
  imported, use a clearly named stub alias so an absent plugin still resolves.
- Register a plugin registry in `components.json` only when that plugin ships
  one. With no package and no environment value, the host must build and run
  unchanged.

Record a needed but unavailable host API as a follow-up in the plugin's
repository-specific instructions; do not invent a host API.
