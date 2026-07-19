# Authentication-client domain policy

`astro-auth-m8` is the authentication foundation. It is required by the host
and every other plugin, owns authentication, and is not reimplemented by
another plugin. Non-auth plugins couple to it only through their
`*AuthAdapter` interface or the `fa-auth-astro` provider, never by importing
its internals.

Its service dependency is the `fa-auth-m8` HTTP contract only (schemas and
version range), never Python source. Contract metadata remains synchronized
with the client schema and compatibility code; do not silently widen the
service-version range.
