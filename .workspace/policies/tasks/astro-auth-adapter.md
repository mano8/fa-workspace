# Astro auth-adapter task

Use this overlay only while wiring or changing an Astro plugin's authentication
adapter. The integration must warn, rather than throw, when `astro-auth-m8` is
absent or ordered after the plugin. When the host uses the adapter, list the
plugin after `faAuth` so it receives `fa-auth-m8` tokens.

For a non-auth plugin, couple only through its declared `*AuthAdapter`
interface or the `fa-auth-astro` provider. Do not import authentication
internals or reimplement authentication.
