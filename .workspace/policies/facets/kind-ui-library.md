# Shared UI-library policy

`astro-ui-m8` owns the shared shadcn registry, design-token bridge, generic
list-parameter helpers, and shared test harness. It is not an Astro
integration and is exempt from the rule that a business client fronts one
service. Business plugins consume it as a normal dependency.
