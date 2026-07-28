"""W9b external, single-use authorization capabilities.

The workspace is deliberately only a carrier for a signed capability.  It
cannot be the trust root: public keys and the one-shot replay store live below
an owner-controlled directory outside the workspace write boundary.  This
module does not write receipts or invoke an agent; callers persist only the
metadata-only :class:`AuthorizationProvenance` returned after redemption.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from agent_context import w2b1


CAPABILITY_FIELDS = {"schema_version", "payload_jcs", "signature"}
PAYLOAD_FIELDS = {
    "schema_version", "authorization_id", "issuer", "key_id", "nonce",
    "issued_at", "expires_at", "launch_id", "repositories", "tasks",
    "operations", "user_task_sha256",
}
TRUST_STORE_FIELDS = {"schema_version", "keys"}
TRUST_KEY_FIELDS = {"issuer", "key_id", "algorithm", "public_key", "status"}
PROVENANCE_FIELDS = {
    "authorization_id", "issuer", "key_id", "signed_payload_sha256",
    "signature_sha256", "issued_at", "expires_at", "redemption_id",
}
REQUEST_FIELDS = {
    "schema_version", "launch_id", "nonce", "repositories", "tasks",
    "operations", "user_task_sha256",
}
MAX_VALIDITY_SECONDS = 15 * 60


def _fail(message: str) -> NoReturn:
    raise w2b1.AgentContextError("E_AUTHORIZATION", message)


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64url(value: Any, field: str) -> bytes:
    if not isinstance(value, str) or not value or "=" in value:
        _fail(f"{field} must be unpadded base64url")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, UnicodeEncodeError) as error:
        _fail(f"{field} is not valid base64url: {error}")
    if _b64url(raw) != value:
        _fail(f"{field} is not canonical base64url")
    return raw


def _closed(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"{name} does not have the closed required shape")
    return value


def _identifier(value: Any, name: str) -> str:
    try:
        w2b1._identifier(value, name)
    except w2b1.AgentContextError as error:
        _fail(error.message)
    return value


def _sha256(value: Any, name: str) -> str:
    try:
        w2b1._sha256(value, name)
    except w2b1.AgentContextError as error:
        _fail(error.message)
    return value


def _canonical_set(value: Any, name: str) -> tuple[str, ...]:
    try:
        w2b1._canonical_set(value, name)
    except w2b1.AgentContextError as error:
        _fail(error.message)
    return tuple(value)


def _timestamp(value: Any, name: str) -> datetime:
    try:
        w2b1._timestamp(value, name)
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, w2b1.AgentContextError) as error:
        _fail(f"{name} is invalid: {error}")


def _canonical_inputs(values: Sequence[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        _fail(f"{name} must be a sequence of identifiers")
    result = tuple(sorted(set(values)))
    if len(result) != len(values):
        _fail(f"{name} must not contain duplicates")
    for value in result:
        _identifier(value, name)
    return result


def user_task_sha256(user_task: str) -> str:
    """Return the exact UTF-8 task hash bound into an authorization request."""
    if not isinstance(user_task, str) or not user_task:
        _fail("user task must be a non-empty string")
    return hashlib.sha256(user_task.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthorizationRequest:
    """Metadata emitted before an external signer approves a launch."""

    launch_id: str
    nonce: str
    repositories: tuple[str, ...]
    tasks: tuple[str, ...]
    operations: tuple[str, ...]
    user_task_sha256: str

    def payload_binding(self) -> dict[str, Any]:
        return {
            "launch_id": self.launch_id,
            "nonce": self.nonce,
            "repositories": list(self.repositories),
            "tasks": list(self.tasks),
            "operations": list(self.operations),
            "user_task_sha256": self.user_task_sha256,
        }

    def as_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, **self.payload_binding()}


def create_request(
    *, repositories: Sequence[str], tasks: Sequence[str], operations: Sequence[str], user_task: str,
    launch_id: str | None = None, nonce: str | None = None,
) -> AuthorizationRequest:
    """Create a launch-bound request; this operation cannot authorize work."""
    launch = launch_id or f"launch-{secrets.token_hex(16)}"
    request_nonce = nonce or f"nonce-{secrets.token_hex(24)}"
    _identifier(launch, "launch_id")
    _identifier(request_nonce, "nonce")
    return AuthorizationRequest(
        launch_id=launch,
        nonce=request_nonce,
        repositories=_canonical_inputs(repositories, "repositories"),
        tasks=_canonical_inputs(tasks, "tasks"),
        operations=_canonical_inputs(operations, "operations"),
        user_task_sha256=user_task_sha256(user_task),
    )


def request_from_capability(
    capability: Mapping[str, Any], *, repositories: Sequence[str],
    tasks: Sequence[str], operations: Sequence[str], user_task: str,
) -> AuthorizationRequest:
    """Reconstruct the exact prepared request carried by a signed capability.

    This performs no authorization.  It extracts only the launch identifier and
    nonce needed to bind the actual invocation before ``verify_and_redeem``
    authenticates and atomically consumes the complete payload.
    """
    supplied = _closed(dict(capability), CAPABILITY_FIELDS, "authorization capability")
    if supplied["schema_version"] != 1 or not isinstance(supplied["payload_jcs"], str):
        _fail("authorization capability version or payload is invalid")
    try:
        payload = w2b1.parse_strict_json(supplied["payload_jcs"].encode("utf-8"))
    except w2b1.AgentContextError as error:
        _fail(f"authorization payload is invalid: {error}")
    payload = _closed(payload, PAYLOAD_FIELDS, "authorization payload")
    return create_request(
        repositories=repositories, tasks=tasks, operations=operations,
        user_task=user_task, launch_id=payload["launch_id"], nonce=payload["nonce"],
    )


@dataclass(frozen=True)
class AuthorizationProvenance:
    """The only authorization data safe to link from manifests and receipts."""

    authorization_id: str
    issuer: str
    key_id: str
    signed_payload_sha256: str
    signature_sha256: str
    issued_at: str
    expires_at: str
    redemption_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "authorization_id": self.authorization_id,
            "issuer": self.issuer,
            "key_id": self.key_id,
            "signed_payload_sha256": self.signed_payload_sha256,
            "signature_sha256": self.signature_sha256,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "redemption_id": self.redemption_id,
        }


@dataclass(frozen=True)
class VerifiedAuthorization:
    """In-memory verified capability and its metadata-only receipt linkage."""

    request: AuthorizationRequest
    provenance: AuthorizationProvenance


def _external_path(
    external_root: Path, path: Path, *, workspace_root: Path, directory: bool,
) -> Path:
    """Resolve an owner-only external path without following any reparse point."""
    try:
        root = external_root.resolve(strict=True)
        workspace = workspace_root.resolve(strict=True)
        try:
            root.relative_to(workspace)
        except ValueError:
            pass
        else:
            _fail("external authorization root must be outside the workspace")
        try:
            workspace.relative_to(root)
        except ValueError:
            pass
        else:
            _fail("external authorization root must not contain the workspace")
        target = path.resolve(strict=True)
        target.relative_to(root)
        relative = target.relative_to(root)
    except (OSError, ValueError) as error:
        _fail(f"external authorization path is unavailable or escapes its root: {error}")
    try:
        root_info = root.lstat()
    except OSError as error:
        _fail(f"external authorization root cannot be inspected: {error}")
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        _fail("external authorization root must be a real directory")
    if os.name == "posix" and (
        root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) & 0o077
    ):
        _fail("external authorization root must be owner-only")
    current = root
    for part in relative.parts:
        current = current / part
        try:
            info = current.lstat()
        except OSError as error:
            _fail(f"external authorization path cannot be inspected: {error}")
        if stat.S_ISLNK(info.st_mode):
            _fail("external authorization paths must not contain symlinks or reparse points")
    try:
        info = target.lstat()
    except OSError as error:
        _fail(f"external authorization path cannot be inspected: {error}")
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode):
        _fail("external authorization path has the wrong file type")
    if os.name == "posix" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
        _fail("external authorization path must be owner-only")
    return target


def _trust_key(
    external_root: Path, trust_store: Path, workspace_root: Path, issuer: str, key_id: str,
) -> bytes:
    path = _external_path(
        external_root, trust_store, workspace_root=workspace_root, directory=False,
    )
    try:
        value = w2b1.parse_strict_json(path.read_bytes())
    except (OSError, w2b1.AgentContextError) as error:
        _fail(f"external trust store is invalid: {error}")
    store = _closed(value, TRUST_STORE_FIELDS, "trust store")
    if store["schema_version"] != 1 or not isinstance(store["keys"], list):
        _fail("trust store version or key list is invalid")
    matching: list[dict[str, Any]] = []
    for value in store["keys"]:
        key = _closed(value, TRUST_KEY_FIELDS, "trust-store key")
        if key["issuer"] == issuer and key["key_id"] == key_id:
            matching.append(key)
    if len(matching) != 1:
        _fail("authorization key is unknown or ambiguous")
    key = matching[0]
    if key["algorithm"] != "ed25519" or key["status"] != "active":
        _fail("authorization key is revoked or uses an unsupported algorithm")
    raw = _unb64url(key["public_key"], "trust-store public_key")
    if len(raw) != 32:
        _fail("trust-store public_key must be an Ed25519 public key")
    return raw


def _consume(
    replay_store: Path, external_root: Path, workspace_root: Path, *,
    identity: str, provenance: AuthorizationProvenance,
) -> None:
    store = _external_path(
        external_root, replay_store, workspace_root=workspace_root, directory=True,
    )
    path = store / f"redeemed-{identity}.json"
    payload = w2b1.canonical_bytes(provenance.as_dict())
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        _fail("authorization capability was already or ambiguously redeemed")
    except OSError as error:
        _fail(f"authorization replay store cannot atomically consume capability: {error}")
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        _fail(f"authorization replay-store persistence is ambiguous: {error}")


def verify_and_redeem(
    capability: Mapping[str, Any], *, request: AuthorizationRequest,
    workspace_root: Path, external_root: Path, trust_store: Path, replay_store: Path,
    now: datetime | None = None,
) -> VerifiedAuthorization:
    """Verify and atomically consume one externally signed authorization.

    The caller must invoke this before any client transport or task submission.
    Once a capability reaches the replay store it is terminal, including when a
    later delivery step fails.
    """
    supplied = _closed(dict(capability), CAPABILITY_FIELDS, "authorization capability")
    if supplied["schema_version"] != 1 or not isinstance(supplied["payload_jcs"], str):
        _fail("authorization capability version or payload is invalid")
    payload_bytes = supplied["payload_jcs"].encode("utf-8")
    try:
        payload = w2b1.parse_strict_json(payload_bytes)
    except w2b1.AgentContextError as error:
        _fail(f"authorization payload is invalid: {error}")
    payload = _closed(payload, PAYLOAD_FIELDS, "authorization payload")
    if w2b1.canonical_bytes(payload) != payload_bytes:
        _fail("authorization payload must use RFC 8785 JCS bytes")
    if payload["schema_version"] != 1:
        _fail("authorization payload schema_version is invalid")
    for field in ("authorization_id", "issuer", "key_id", "nonce", "launch_id"):
        _identifier(payload[field], f"authorization payload {field}")
    for field in ("repositories", "tasks", "operations"):
        _canonical_set(payload[field], f"authorization payload {field}")
    _sha256(payload["user_task_sha256"], "authorization payload user_task_sha256")
    issued = _timestamp(payload["issued_at"], "authorization payload issued_at")
    expires = _timestamp(payload["expires_at"], "authorization payload expires_at")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        _fail("authorization clock must be timezone-aware")
    if issued > current or expires <= current or expires <= issued:
        _fail("authorization capability is future-dated or expired")
    if (expires - issued).total_seconds() > MAX_VALIDITY_SECONDS:
        _fail("authorization capability validity exceeds fifteen minutes")
    expected = request.payload_binding()
    for field, value in expected.items():
        if payload[field] != value:
            _fail(f"authorization capability {field} does not match its launch request")
    public_key = _trust_key(
        external_root, trust_store, workspace_root, payload["issuer"], payload["key_id"],
    )
    signature = _unb64url(supplied["signature"], "authorization signature")
    if len(signature) != 64:
        _fail("authorization signature must be an Ed25519 signature")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, payload_bytes)
    except (InvalidSignature, ValueError) as error:
        _fail(f"authorization signature is invalid: {type(error).__name__}")
    payload_digest = hashlib.sha256(payload_bytes).hexdigest()
    signature_digest = hashlib.sha256(signature).hexdigest()
    identity = hashlib.sha256(
        (payload["issuer"] + "\x00" + payload["key_id"] + "\x00" + payload["authorization_id"] + "\x00" + payload["nonce"]).encode("utf-8")
    ).hexdigest()
    provenance = AuthorizationProvenance(
        authorization_id=payload["authorization_id"], issuer=payload["issuer"], key_id=payload["key_id"],
        signed_payload_sha256=payload_digest, signature_sha256=signature_digest,
        issued_at=payload["issued_at"], expires_at=payload["expires_at"], redemption_id=identity,
    )
    _consume(
        replay_store, external_root, workspace_root,
        identity=identity, provenance=provenance,
    )
    return VerifiedAuthorization(request=request, provenance=provenance)


def load_capability(root: Path, value: str) -> dict[str, Any]:
    """Load one signed carrier without permitting a pointer outside the workspace."""
    try:
        w2b1._canonical_path(value, "authorization path")
        candidate = root.joinpath(*value.split("/"))
        info = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError, w2b1.AgentContextError) as error:
        raise w2b1.AgentContextError(
            "E_SCOPE_UNAVAILABLE", f"authorization capability path is unsafe: {error}"
        ) from error
    if candidate != resolved or not info or candidate.is_symlink() or not candidate.is_file():
        raise w2b1.AgentContextError(
            "E_SCOPE_UNAVAILABLE", "authorization capability must be a regular workspace-relative file"
        )
    try:
        parsed = w2b1.parse_strict_json(candidate.read_bytes())
    except (OSError, UnicodeDecodeError, w2b1.AgentContextError) as error:
        _fail(f"authorization capability is invalid: {error}")
    if not isinstance(parsed, dict):
        _fail("authorization capability must be a JSON object")
    return parsed


def verify_authorizations(
    *, root: Path, capabilities: Sequence[Mapping[str, Any]], repositories: Sequence[str],
    tasks: Sequence[str], operations: Sequence[str], prompt: str,
    external_root: Path | None, trust_store: Path | None, replay_store: Path | None,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, str], ...], str | None, Path | None]:
    """Authenticate and consume every signed capability before adapter preflight.

    Both canonical launchers call this one boundary, so no client-specific path
    can redeem a capability differently or reach a transport without it.
    """
    external_values = (external_root, trust_store, replay_store)
    if not capabilities:
        if any(value is not None for value in external_values):
            raise w2b1.AgentContextError(
                "E_USAGE", "external authorization paths require a signed capability"
            )
        return (), (), None, None
    if any(value is None for value in external_values):
        _fail("signed capabilities require external root, trust store, and replay store")
    assert external_root is not None and trust_store is not None and replay_store is not None
    resolved_trust_store = trust_store if trust_store.is_absolute() else external_root / trust_store
    resolved_replay_store = replay_store if replay_store.is_absolute() else external_root / replay_store
    records: list[dict[str, Any]] = []
    provenance: list[dict[str, str]] = []
    launch_ids: set[str] = set()
    for capability in capabilities:
        request = request_from_capability(
            capability, repositories=repositories, tasks=tasks,
            operations=operations, user_task=prompt,
        )
        verified = verify_and_redeem(
            capability, request=request, workspace_root=root, external_root=external_root,
            trust_store=resolved_trust_store, replay_store=resolved_replay_store,
        )
        item = verified.provenance.as_dict()
        launch_ids.add(request.launch_id)
        provenance.append(item)
        records.append({
            "authorization_id": item["authorization_id"],
            "kind": "named-owner-decision",
            "authorized_by": item["issuer"],
            "source_ref": f"ed25519:{item['key_id']}:{item['redemption_id']}",
            "source_sha256": item["signed_payload_sha256"],
            "repositories": list(request.repositories),
            "operations": list(request.operations),
            "issued_at": item["issued_at"],
        })
    if len(launch_ids) != 1:
        _fail("all signed capabilities must bind the same launch_id")
    ordered = sorted(zip(records, provenance, strict=True), key=lambda pair: pair[0]["authorization_id"])
    return (
        tuple(pair[0] for pair in ordered),
        tuple(pair[1] for pair in ordered),
        next(iter(launch_ids)),
        resolved_trust_store,
    )
