# FastAPI framework policy

- Validate all untrusted request input — path, query, body, and header — at
  the route boundary using typed request/response models before it reaches
  application logic
  ([`SEC-VALIDATE-UNTRUSTED-INPUT`](../../architecture.md#sec-validate-untrusted-input)).
- Keep routers and dependencies as the transport layer only; business logic
  lives outside them and is called, not duplicated, composing with the
  business-logic/transport separation in
  [`kind-api-service.md`](kind-api-service.md).
- Validate required startup and lifespan configuration before the application
  begins serving requests.
- Return consistent, typed error responses for a given failure category
  instead of ad hoc per-route error shapes.
