"""Content-bound reviewed-tree identity for the required Codex launch mode.

The identity is deliberately assembled from exact bytes and command output, not
from a working-directory name or a receipt.  It is transient until a launcher
places its digest in a session/receipt; it never contains configuration content
or secrets.
"""

from __future__ import annotations

import hashlib
import os
import platform
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_context import w2b1


ZERO_SHA256 = "0" * 64

# These are the root-owned executable/configuration inputs that can change the
# canonical Codex result.  A directory glob is used only for the workspace
# contract collection, and each resolved member must be a tracked regular file.
CRITICAL_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    ".m8-workspace-root",
    ".codex/config.toml",
    ".workspace/repo-types.json",
    ".workspace/policy.index.json",
    ".workspace/policy.metadata.json",
    ".workspace/contracts",
    "scripts/agent_context/authorization.py",
    "scripts/agent_context/codex_adapter.py",
    "scripts/agent_context/codex_repo_launcher.py",
    "scripts/agent_context/delivery_kernel.py",
    "scripts/agent_context/resolve_context.py",
    "scripts/agent_context/shared_validation.py",
    "scripts/agent_context/validate_workspace.py",
    "scripts/codex-repo.sh",
    "scripts/codex-repo.ps1",
    ".devcontainer/devcontainer.json",
    ".devcontainer/devcontainer-lock.json",
    ".devcontainer/docker-compose.devcontainer.yml",
    ".devcontainer/setup.sh",
    ".devcontainer/configure-mcp.sh",
)


def _fail(code: str, message: str) -> None:
    raise w2b1.AgentContextError(code, message)


def _sha256(path: Path, *, code: str = "E_TRUST") -> str:
    try:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            _fail(code, f"trust input is not a regular file: {path}")
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        _fail(code, f"cannot hash trust input {path}: {error}")


def _run(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("git", *arguments), cwd=root, check=False, capture_output=True,
    )
    if result.returncode != 0:
        _fail("E_TRUST", f"Git trust preflight failed for {' '.join(arguments)}")
    try:
        return result.stdout.decode("ascii", "strict").strip()
    except UnicodeDecodeError:
        _fail("E_TRUST", "Git trust preflight returned non-ASCII identity data")


def _git_identity(root: Path) -> dict[str, str]:
    top_level = _run(root, "rev-parse", "--show-toplevel")
    try:
        if Path(top_level).resolve(strict=True) != root.resolve(strict=True):
            _fail("E_TRUST", "Git identity belongs to a parent checkout, not this selected root")
    except OSError as error:
        _fail("E_TRUST", f"Git identity root cannot be resolved: {error}")
    status = _run(root, "status", "--porcelain=v1", "--untracked-files=no")
    if status:
        _fail("E_TRUST", "tracked workspace content is dirty or staged")
    head = _run(root, "rev-parse", "HEAD")
    tree = _run(root, "rev-parse", "HEAD^{tree}")
    if len(head) not in {40, 64} or len(tree) not in {40, 64}:
        _fail("E_TRUST", "Git trust identity has an unsupported object format")
    return {"commit": head, "tree": tree}


def _tracked_files(root: Path, relative: str) -> list[str]:
    candidate = root.joinpath(*relative.split("/"))
    try:
        info = candidate.lstat()
    except OSError as error:
        _fail("E_TRUST", f"critical trust input is missing: {relative}: {error}")
    if stat.S_ISLNK(info.st_mode):
        _fail("E_TRUST", f"critical trust input is a symlink: {relative}")
    if stat.S_ISREG(info.st_mode):
        tracked = _run(root, "ls-files", "--error-unmatch", "--", relative)
        if tracked != relative:
            _fail("E_TRUST", f"critical trust input is not tracked: {relative}")
        return [relative]
    if not stat.S_ISDIR(info.st_mode):
        _fail("E_TRUST", f"critical trust input is not a regular file/directory: {relative}")
    tracked = _run(root, "ls-files", "--", relative).splitlines()
    files = [item for item in tracked if item and (candidate / item[len(relative):].lstrip("/")).is_file()]
    if not files:
        _fail("E_TRUST", f"critical trust directory has no tracked files: {relative}")
    return files


def _critical_hashes(root: Path, capability_path: str) -> list[dict[str, str]]:
    paths = list(CRITICAL_PATHS) + [capability_path]
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for relative in paths:
        try:
            w2b1._canonical_path(relative, "trust input path")
        except w2b1.AgentContextError:
            _fail("E_TRUST", f"invalid trust input path: {relative}")
        for item in _tracked_files(root, relative):
            if item in seen:
                continue
            seen.add(item)
            result.append({"path": item, "sha256": _sha256(root / item)})
    return sorted(result, key=lambda item: item["path"])


def _config_inventory(root: Path, codex_home: Path) -> list[dict[str, str | None]]:
    """Inventory paths that affect Codex without recording their contents."""
    paths = (
        ("project", root / ".codex" / "config.toml"),
        ("user", codex_home / "config.toml"),
        # Codex has no separate global configuration path in the frozen mode;
        # making that absence explicit prevents an ambient, undocumented input.
        ("global", Path("/etc/codex/config.toml")),
    )
    values: list[dict[str, str | None]] = []
    for kind, path in paths:
        try:
            info = path.lstat()
        except FileNotFoundError:
            values.append({"kind": kind, "path": f"{kind}:config.toml", "sha256": None})
            continue
        except OSError as error:
            _fail("E_TRUST", f"cannot inspect {kind} Codex configuration: {error}")
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            _fail("E_TRUST", f"{kind} Codex configuration is not a regular file")
        values.append({"kind": kind, "path": f"{kind}:config.toml", "sha256": _sha256(path)})
    return values


def _binary_identity(path: Path, version: str) -> dict[str, str]:
    return {"path": str(path), "sha256": _sha256(path), "version": version}


def build_trust_identity(
    *,
    workspace_root: Path,
    selected_repositories: Sequence[Path],
    capability_path: str,
    codex_binary: Path,
    codex_version: str,
    authorization_trust_store: Path | None = None,
) -> dict[str, Any]:
    """Return a JCS-addressed identity after fail-closed trust preflight.

    The caller must provide repository paths discovered from the central
    registry.  Each is independently Git-bound, so a parent receipt/tree
    cannot stand in for a child repository's identity.
    """
    try:
        root = workspace_root.resolve(strict=True)
    except OSError as error:
        _fail("E_TRUST", f"workspace root cannot be resolved: {error}")
    root_git = _git_identity(root)
    children: list[dict[str, Any]] = []
    for repository in sorted(selected_repositories, key=lambda item: item.name):
        try:
            candidate = repository.resolve(strict=True)
            candidate.relative_to(root)
        except (OSError, ValueError) as error:
            _fail("E_TRUST", f"selected child is outside the workspace: {error}")
        instruction = candidate / "AGENTS.md"
        children.append({
            "path": candidate.relative_to(root).as_posix(),
            "git": _git_identity(candidate),
            "instruction_sha256": _sha256(instruction),
        })
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    python_path = Path(sys.executable).resolve()
    trust_store_hash = None
    if authorization_trust_store is not None:
        trust_store_hash = _sha256(authorization_trust_store)
    identity: dict[str, Any] = {
        "schema_version": 1,
        "root": root_git,
        "children": children,
        "critical_files": _critical_hashes(root, capability_path),
        "codex": _binary_identity(codex_binary, codex_version),
        "python": _binary_identity(python_path, platform.python_version()),
        "platform": {
            "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "python_implementation": platform.python_implementation(),
        },
        "configuration": _config_inventory(root, codex_home),
        "authorization_trust_store_sha256": trust_store_hash,
        "trust_identity_sha256": ZERO_SHA256,
    }
    identity["trust_identity_sha256"] = w2b1.canonical_sha256(
        {key: value for key, value in identity.items() if key != "trust_identity_sha256"}
    )
    return identity


def verify_trust_identity(expected: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Recompute every live trust input and reject any exact identity drift."""
    supplied = expected.get("trust_identity_sha256") if isinstance(expected, Mapping) else None
    try:
        w2b1._sha256(supplied, "trust identity")
    except w2b1.AgentContextError:
        _fail("E_TRUST", "preflight trust identity is invalid")
    current = build_trust_identity(**kwargs)
    if current["trust_identity_sha256"] != supplied or dict(expected) != current:
        _fail("E_TRUST", "reviewed trust identity drifted after preflight")
    return current
