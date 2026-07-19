# Astro plugin-testing task

Use this overlay while validating a changed Astro integration package. Select
the repository's package manager from `packageManager` and lockfiles, then run
the child-owned build, typecheck, test, and coverage gates that apply.

Verify standalone installability in a fresh Astro fixture: run `build` and
`build:registry` when provided, create a package tarball, and perform an
install-from-tarball smoke test. Exercise both starter routes and headless
composition when the change can affect either mode.
