# Authentication-security domain policy

- Never emit credentials, tokens, keys, or session material in logs, errors,
  traces, metrics, or responses; identify a principal by a non-secret
  identifier instead
  ([`SEC-NO-SECRET-DISCLOSURE`](../../architecture.md#sec-no-secret-disclosure)).
- Take signing keys, client secrets, and provider credentials only from an
  ignored environment file, an approved vault, or the system credential
  manager — never from a tracked file, fixture, or built-in default
  ([`SEC-NO-TRACKED-SECRETS`](../../architecture.md#sec-no-tracked-secrets)).
- Validate untrusted auth input — credentials, tokens, headers, callback and
  redirect targets — at the auth boundary before it reaches authentication or
  authorization logic
  ([`SEC-VALIDATE-UNTRUSTED-INPUT`](../../architecture.md#sec-validate-untrusted-input)).
- Verify a token or session — signature, issuer, audience, and expiry — before
  trusting any of its claims for identity or authorization.
- Fail closed: deny when a check cannot be completed or its inputs cannot be
  verified, and decide authorization where the trust boundary is owned.
- Bound token and session lifetime, and support revocation and rotation of
  issued material and signing keys.
