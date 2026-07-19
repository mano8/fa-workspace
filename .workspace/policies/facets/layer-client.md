# Client-layer policy

- Keep UI stateful behavior isolated from service access; client API access
  stays behind a contract-bound client boundary.
- A client is stateless with no business logic beyond its service contract.
