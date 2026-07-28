"""Step 12.3 fail-closed Claude launcher-adapter.

These tests are offline.  They never invoke the Claude client, never contact a
vendor API, and never write outside a temporary directory.  The native-load
inspection and the client process are supplied through the adapter's own seams,
which is exactly how a canonical launch keeps them separable: evidence comes
from a real capture, and this suite proves what the adapter does with it.

The suite covers the whole ordered path — preflight, resolution, native/inject
classification, channel selection by ``model_visible_total``, delivery, and the
kernel lifecycle — and one frozen reproduction against the live workspace tree.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import claude_delivery_adapter as adapter
from agent_context import claude_native_evidence as native
from agent_context import claude_repo_launcher, w2b1
from agent_context.codex_adapter import CommandResult
from agent_context.delivery_kernel import DeliveryKernel


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = "scripts/agent_context/fixtures/evidence"
NATIVE_EVIDENCE = ROOT / EVIDENCE_DIR / "w12-claude-native-load-evidence-2026-07-28.json"
CAPABILITY = ROOT / EVIDENCE_DIR / "w12-claude-capability-evidence-2026-07-27.json"
ADAPTER_EVIDENCE = ROOT / EVIDENCE_DIR / "w12-claude-adapter-evidence-2026-07-28.json"
ADAPTER_REPORT = ROOT / EVIDENCE_DIR / "w12-claude-adapter-evidence-2026-07-28.md"
HOOK_ROW = "claude-devcontainer-non-interactive-hook-additional-context"
FULL_ROW = "claude-devcontainer-non-interactive-append-system-prompt"
SECTION_PREAMBLE = (
    "<system-reminder>\nAs you answer the user's questions, you can use the following context:\n"
    "# claudeMd\nCodebase and user instructions are shown below.\n\n"
)
SYNTHETIC_TREE = {"algorithm": "git-sha1", "value": "b" * 40}


def _capture_text(root: Path, paths: tuple[str, ...]) -> str:
    """Rebuild the client's observed project-memory framing for a fixture."""
    blocks = [SECTION_PREAMBLE]
    for path in paths:
        content = (root / path).read_text(encoding="utf-8")
        blocks.append(
            f"Contents of {root / path} (project instructions, checked into the codebase):\n\n"
            f"{content}\n"
        )
    return "".join(blocks) + "# userEmail\nnobody\n"


def _load(
    root: Path, paths: tuple[str, ...], *, settings: dict[str, object] | None = None,
    project: str = ".", captured_at: str = "2026-07-28T00:00:00Z",
    client_sha256: str = "a" * 64, client_identity: str = "/opt/claude/2.1.220",
    client_version: str = "2.1.220 (Claude Code)", trust_state: str = "trusted",
) -> native.ClaudeNativeLoad:
    """Build one recorded native-load result without launching a client."""
    text = _capture_text(root, paths)
    sources, external = native.parse_active_sources([text], root)
    layer = settings if settings is not None else {"project": {}, "user": None, "registered_hook_events": []}
    return native.ClaudeNativeLoad(
        mechanism=native.MECHANISM, workspace_root=root.resolve(strict=True), project=project,
        client_identity=client_identity, client_version=client_version, client_sha256=client_sha256,
        trust_state=trust_state, settings=layer, config_sha256=w2b1.canonical_sha256(layer),
        captured_at=captured_at, sources=sources, external_labels=external, request_count=1,
        model_input_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        model_input_bytes=len(text.encode("utf-8")), visible_text=text,
    )


class W12ClaudeAdapterFixtureTests(unittest.TestCase):
    """The ordered preflight, classification, and delivery path of one launch."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "workspace"
        self.root.mkdir()
        self.home = self.base / "home"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
        (self.root / ".m8-workspace-root").write_text("m8-workspace-v2\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# workspace bootstrap\n", encoding="utf-8")
        (self.root / ".claude").mkdir()
        shutil.copy2(ROOT / ".claude" / "settings.json", self.root / ".claude" / "settings.json")
        self.container = self.base / "dockerenv"
        self.container.write_text("", encoding="utf-8")
        self._write_workspace_configuration()
        self.child = self.root / "repo-a"
        (self.child / ".git").mkdir(parents=True)
        (self.child / "CLAUDE.md").write_text("# child memory\n", encoding="utf-8")
        (self.child / "REPOSITORY_CONTEXT.md").write_text("# neutral child context\n", encoding="utf-8")
        evidence = self.root / EVIDENCE_DIR
        evidence.mkdir(parents=True)
        for source in (CAPABILITY, NATIVE_EVIDENCE):
            shutil.copy2(source, evidence / source.name)
        self.artifact = json.loads(CAPABILITY.read_text(encoding="utf-8"))
        self.client = self.artifact["client"]
        self._write_trust_record(trusted=True)
        self.commands: list[tuple[str, ...]] = []
        self.session_id: str | None = None
        self.returncode = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    # ------------------------------------------------------------------ fixture

    def _write_workspace_configuration(self) -> None:
        workspace = self.root / ".workspace"
        policies = workspace / "policies"
        policies.mkdir(parents=True)
        (policies / "always.md").write_text("always policy\n", encoding="utf-8")
        (policies / "python.md").write_text("python facet policy\n", encoding="utf-8")
        (workspace / "repo-types.json").write_text(json.dumps({
            "schema_version": 2, "repositories": [{
                "id": "repo-a", "path": "repo-a", "kind": "sdk", "layer": "platform",
                "facets": ["python"],
            }],
        }), encoding="utf-8")
        (workspace / "policy.index.json").write_text(json.dumps({
            "schema_version": 2, "mode": "faceted",
            "budgets": {"preferred_bytes": 24576, "hard_bytes": 32768},
            "always": ["always.policy"], "facet_ids": ["python"],
            "facets": {"python": ["python.policy"]},
            "tasks": {"git-commit": {"policies": ["always.policy"], "authorization": "mutating"}},
            "exclusions": {},
        }), encoding="utf-8")
        (workspace / "policy.metadata.json").write_text(json.dumps({
            "units": [
                self._unit("always.policy", ".workspace/policies/always.md", True),
                self._unit("python.policy", ".workspace/policies/python.md", False),
            ], "invariants": ["OWNERSHIP"], "capabilities": [],
        }), encoding="utf-8")

    @staticmethod
    def _unit(policy_id: str, path: str, required: bool) -> dict[str, object]:
        return {
            "id": policy_id, "path": path, "authority_tier": "workspace",
            "scope": {"repository_id": "$workspace", "prefix": "."},
            "invariant_ids": ["OWNERSHIP"], "conflicts_with": [], "may_override": [],
            "required": required, "capabilities_granted": [],
        }

    def _register_hooks(self, *events: str) -> None:
        """Register real additionalContext hooks in the local settings layer.

        The reviewed project settings file forbids hooks, so a launcher-visible
        hook can only arrive through the ignored local or user layer.
        """
        (self.root / ".claude" / "settings.local.json").write_text(
            json.dumps({"hooks": {
                event: [{"hooks": [{"type": "command", "command": "true"}]}] for event in events
            }}),
            encoding="utf-8",
        )

    def _write_trust_record(self, *, trusted: bool, scope: Path | None = None) -> None:
        (self.home / ".claude.json").write_text(
            json.dumps({"projects": {str(scope or self.root): {"hasTrustDialogAccepted": trusted}}}),
            encoding="utf-8",
        )

    def _runner(self, command: tuple[str, ...] | list[str], cwd: Path) -> CommandResult:
        del cwd
        self.commands.append(tuple(command))
        index = list(command).index("--session-id" if "--session-id" in command else "--resume")
        session = self.session_id or command[index + 1]
        return CommandResult(self.returncode, json.dumps({"session_id": session}).encode("utf-8"))

    def _inspector(self, **kwargs: object) -> native.ClaudeNativeLoad:
        project = Path(str(kwargs["project"]))
        paths = ("CLAUDE.md",) if project == self.root else (
            "CLAUDE.md", "repo-a/CLAUDE.md", "repo-a/REPOSITORY_CONTEXT.md"
        )
        return _load(
            self.root, paths, project="." if project == self.root else project.name,
            settings=native.settings_identity(self.root, home=self.home),
            client_identity=self.client["resolved_path"], client_version=self.client["version"],
            client_sha256=self.client["sha256"],
            trust_state=native.trust_state(project, home=self.home),
        )

    def _adapter(self, **kwargs: object) -> adapter.ClaudeLauncherAdapter:
        return adapter.ClaudeLauncherAdapter(
            runner=self._runner, client_command="fixture-claude", inspector=self._inspector, **kwargs
        )

    def _environment(self):
        return mock.patch.dict(os.environ, {"HOME": str(self.home)})

    def _patches(self):
        return mock.patch.multiple(
            "agent_context.claude_delivery_adapter",
            CONTAINER_MARKER=self.container,
            _reviewed_tree=lambda _root: dict(SYNTHETIC_TREE),
        )

    def _client_patch(self):
        return mock.patch.object(
            native, "client_identity",
            return_value=(self.client["resolved_path"], self.client["version"], self.client["sha256"]),
        )

    def _resolve(self, **kwargs: object):
        with self._patches(), self._client_patch(), self._environment():
            return self._adapter().resolve_repositories(
                workspace_root=self.root, repository_ids=("repo-a",), **kwargs
            )

    # ---------------------------------------------------------------- preflight

    def test_preflight_proves_client_trust_settings_and_native_load_in_order(self) -> None:
        with self._patches(), self._client_patch(), self._environment():
            preflight = self._adapter().preflight(
                workspace_root=self.root, repository_ids=("repo-a",)
            )
        self.assertEqual(preflight.workspace_root, self.root)
        self.assertEqual(preflight.launch_scope, self.root)
        self.assertEqual(preflight.project, ".")
        self.assertEqual(preflight.repositories, (self.child,))
        self.assertEqual(preflight.trust_state, "trusted")
        self.assertEqual(preflight.client_sha256, self.client["sha256"])
        self.assertEqual(list(preflight.native_source_sha256), ["CLAUDE.md"])
        self.assertEqual(preflight.trust_identity, {})

    def test_every_preflight_stage_fails_closed_with_its_own_code(self) -> None:
        cases: list[tuple[str, str, object]] = [
            ("E_UNSUPPORTED_MODE", "devcontainer", lambda: self.container.unlink()),
            ("E_SCOPE_UNAVAILABLE", ".m8-workspace-root", lambda: (
                (self.root / ".m8-workspace-root").unlink()
            )),
            ("E_CAPABILITY", "capability evidence changed", lambda: (
                (self.root / EVIDENCE_DIR / CAPABILITY.name).write_text("{}\n", encoding="utf-8")
            )),
            ("E_NATIVE_EVIDENCE", "native-load evidence changed", lambda: (
                (self.root / EVIDENCE_DIR / NATIVE_EVIDENCE.name).write_text("{}\n", encoding="utf-8")
            )),
            ("E_TRUST", "reviewed layer", lambda: (
                (self.root / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
            )),
            ("E_TRUST", "not trusted", lambda: self._write_trust_record(trusted=False)),
            ("E_NATIVE_EVIDENCE", "native CLAUDE.md", lambda: (self.child / "CLAUDE.md").unlink()),
            ("E_SCOPE_UNAVAILABLE", ".git", lambda: (self.child / ".git").rmdir()),
        ]
        for code, fragment, mutate in cases:
            with self.subTest(code=code, fragment=fragment):
                self.tearDown()
                self.setUp()
                mutate()
                with self._patches(), self._client_patch(), self._environment():
                    with self.assertRaises(w2b1.AgentContextError) as failure:
                        self._adapter().preflight(
                            workspace_root=self.root, repository_ids=("repo-a",)
                        )
                self.assertEqual(failure.exception.code, code)
                self.assertIn(fragment, failure.exception.message)

    def test_a_changed_installed_client_can_never_reach_resolution(self) -> None:
        for value, code in (
            ({"sha256": "f" * 64}, "E_CAPABILITY"),
            ({"resolved_path": "/opt/other/claude"}, "E_CAPABILITY"),
            ({"version": "2.0.0 (Claude Code)"}, "E_CAPABILITY"),
        ):
            with self.subTest(field=sorted(value)[0]):
                identity = {**self.client, **value}
                with self._patches(), self._environment(), mock.patch.object(
                    native, "client_identity",
                    return_value=(identity["resolved_path"], identity["version"], identity["sha256"]),
                ):
                    with self.assertRaises(w2b1.AgentContextError) as failure:
                        self._adapter().preflight(
                            workspace_root=self.root, repository_ids=("repo-a",)
                        )
                self.assertEqual(failure.exception.code, code)
                self.assertIn("capability evidence", failure.exception.message)

    def test_an_untrusted_child_launch_scope_blocks_the_task(self) -> None:
        with self._patches(), self._client_patch(), self._environment():
            with self.assertRaises(w2b1.AgentContextError) as failure:
                self._adapter().preflight(
                    workspace_root=self.root, repository_ids=("repo-a",), project="repo-a",
                )
        self.assertEqual(failure.exception.code, "E_TRUST")
        self.assertIn("unrecorded", failure.exception.message)
        # A human trust decision, and only that, unblocks the child topology.
        (self.home / ".claude.json").write_text(json.dumps({"projects": {
            str(self.root): {"hasTrustDialogAccepted": True},
            str(self.child): {"hasTrustDialogAccepted": True},
        }}), encoding="utf-8")
        with self._patches(), self._client_patch(), self._environment():
            preflight = self._adapter().preflight(
                workspace_root=self.root, repository_ids=("repo-a",), project="repo-a",
            )
        self.assertEqual(preflight.launch_scope, self.child)
        self.assertEqual(
            sorted(preflight.native_source_sha256),
            ["CLAUDE.md", "repo-a/CLAUDE.md", "repo-a/REPOSITORY_CONTEXT.md"],
        )

    def test_a_settings_change_during_inspection_invalidates_the_capture(self) -> None:
        stale = {"project": {}, "user": None, "registered_hook_events": []}
        with self._patches(), self._client_patch(), self._environment(), mock.patch.object(
            self, "_inspector",
            lambda **kwargs: _load(
                self.root, ("CLAUDE.md",), settings=stale,
                client_identity=self.client["resolved_path"], client_version=self.client["version"],
                client_sha256=self.client["sha256"],
            ),
        ):
            with self.assertRaises(w2b1.AgentContextError) as failure:
                self._adapter().preflight(workspace_root=self.root, repository_ids=("repo-a",))
        self.assertEqual(failure.exception.code, "E_TRUST")
        self.assertIn("settings layer changed", failure.exception.message)

    def test_an_unselected_launch_scope_is_out_of_scope(self) -> None:
        with self._patches(), self._client_patch(), self._environment():
            with self.assertRaises(w2b1.AgentContextError) as failure:
                self._adapter().preflight(
                    workspace_root=self.root, repository_ids=("repo-a",), project="repo-b",
                )
        self.assertEqual(failure.exception.code, "E_SCOPE_UNAVAILABLE")

    # ----------------------------------------------------- classification

    def test_root_scope_classifies_child_instructions_as_proven_absent_injections(self) -> None:
        resolution, preflight = self._resolve()
        entries = {entry["path"]: entry for entry in resolution.resolved.manifest["entries"]}
        self.assertEqual(entries["CLAUDE.md"]["delivery"], "native")
        self.assertEqual(
            entries["CLAUDE.md"]["native_evidence_id"],
            resolution.native_evidence["native_evidence_id"],
        )
        for path in ("repo-a/CLAUDE.md", "repo-a/REPOSITORY_CONTEXT.md",
                     ".workspace/policies/always.md", ".workspace/policies/python.md"):
            self.assertEqual(entries[path]["delivery"], "inject", path)
            self.assertIsNone(entries[path]["native_evidence_id"], path)
        proved = {item["path"] for item in resolution.injection_evidence["sources"]}
        self.assertTrue({"repo-a/CLAUDE.md", "repo-a/REPOSITORY_CONTEXT.md"}.issubset(proved))
        self.assertEqual(preflight.load.source_sha256["CLAUDE.md"], entries["CLAUDE.md"]["source_sha256"])

    def test_a_trusted_child_scope_makes_its_instructions_native_instead(self) -> None:
        (self.home / ".claude.json").write_text(json.dumps({"projects": {
            str(self.root): {"hasTrustDialogAccepted": True},
            str(self.child): {"hasTrustDialogAccepted": True},
        }}), encoding="utf-8")
        resolution, _ = self._resolve(project="repo-a")
        entries = {entry["path"]: entry for entry in resolution.resolved.manifest["entries"]}
        for path in ("CLAUDE.md", "repo-a/CLAUDE.md", "repo-a/REPOSITORY_CONTEXT.md"):
            self.assertEqual(entries[path]["delivery"], "native", path)
        proved = {item["path"] for item in resolution.injection_evidence["sources"]}
        self.assertNotIn("repo-a/CLAUDE.md", proved)

    def test_a_manifest_that_shadows_proven_native_load_fails_closed(self) -> None:
        original = native.verify_manifest_native_binding

        def _shadow(manifest, evidence):
            broken = {**manifest, "entries": [
                {**entry, "delivery": "inject", "native_evidence_id": None}
                if entry["path"] == "CLAUDE.md" else entry
                for entry in manifest["entries"]
            ]}
            return original(broken, evidence)

        with mock.patch.object(native, "verify_manifest_native_binding", _shadow):
            with self.assertRaises(w2b1.AgentContextError) as failure:
                self._resolve()
        self.assertEqual(failure.exception.code, "E_NATIVE_EVIDENCE")

    # -------------------------------------------------------- channel selection

    def test_the_hook_row_is_rejected_until_step_12_4_freezes_its_round_trip(self) -> None:
        resolution, _ = self._resolve()
        self.assertEqual(resolution.capability.row_id, FULL_ROW)
        self.assertEqual(resolution.channel_id, adapter.FULL_CONTENT_CHANNEL_ID)
        self.assertEqual([item["row_id"] for item in resolution.rejected_rows], [HOOK_ROW])
        self.assertIn("round-trip evidence", resolution.rejected_rows[0]["reason"])
        self.assertIsNone(adapter.HOOK_ROUND_TRIP_EVIDENCE)

    def test_a_wired_hook_row_is_selected_only_while_the_total_fits(self) -> None:
        self._register_hooks("UserPromptSubmit")
        with mock.patch.object(adapter, "HOOK_ROUND_TRIP_EVIDENCE", "e" * 64):
            resolution, _ = self._resolve()
            self.assertEqual(resolution.capability.row_id, HOOK_ROW)
            self.assertEqual(resolution.channel_id, adapter.HOOK_CHANNEL_ID)
            accounting = resolution.resolved.manifest["accounting"]
            self.assertLessEqual(accounting["model_visible_total"], accounting["effective_hard_limit"])
            # Once the total no longer fits, a still-registered hook cannot be
            # bypassed by the wrapper channel: that would inject twice.
            (self.root / ".workspace" / "policies" / "python.md").write_text(
                "python facet policy\n" + "x" * 10000, encoding="utf-8"
            )
            with self.assertRaises(w2b1.AgentContextError) as failure:
                self._resolve()
            self.assertEqual(failure.exception.code, "E_CHANNEL")
            self.assertIn("second copy", failure.exception.message)
            # With no hook registered the same oversize generation falls through
            # to the separately tested full-content channel, as Step 12.2 froze.
            (self.root / ".claude" / "settings.local.json").unlink()
            oversized, _ = self._resolve()
        self.assertEqual(oversized.capability.row_id, FULL_ROW)
        self.assertEqual([item["row_id"] for item in oversized.rejected_rows], [HOOK_ROW])
        self.assertIn("E_BUDGET", oversized.rejected_rows[0]["reason"])

    def test_no_fitting_channel_fails_closed_before_any_client_invocation(self) -> None:
        (self.root / ".workspace" / "policies" / "python.md").write_text(
            "python facet policy\n" + "y" * 40000, encoding="utf-8"
        )
        with self.assertRaises(w2b1.AgentContextError) as failure:
            self._resolve()
        self.assertEqual(failure.exception.code, "E_BUDGET")
        self.assertEqual(self.commands, [])

    def test_two_registered_additional_context_events_are_rejected_not_deduplicated(self) -> None:
        self._register_hooks(*native.DUPLICATE_INJECTION_EVENTS)
        with self.assertRaises(w2b1.AgentContextError) as failure:
            self._resolve()
        self.assertEqual(failure.exception.code, "E_CHANNEL")
        self.assertEqual(self.commands, [])

    # ---------------------------------------------------------------- delivery

    def test_one_handoff_delivers_the_exact_envelope_and_completes_the_receipt(self) -> None:
        with self._patches(), self._client_patch(), self._environment():
            result = self._adapter().prepare_and_handoff_repositories(
                workspace_root=self.root, repository_ids=("repo-a",), prompt="inspect the repository",
            )
        self.assertEqual(result.receipt["state"], "COMPLETED")
        self.assertEqual(result.receipt["previous_state"], "SUBMISSION_STARTED")
        self.assertEqual(result.receipt["channel_id"], adapter.FULL_CONTENT_CHANNEL_ID)
        self.assertEqual(result.session["state"], "COMPLETED")
        self.assertEqual(len(self.commands), 1)
        command = self.commands[0]
        self.assertEqual(command[0], "fixture-claude")
        self.assertIn("--append-system-prompt", command)
        envelope = command[command.index("--append-system-prompt") + 1].encode("utf-8")
        self.assertEqual(hashlib.sha256(envelope).hexdigest(), result.receipt["envelope_sha256"])
        self.assertEqual(len(envelope), result.receipt["delivered_bytes"])
        self.assertEqual(command[command.index("--session-id") + 1], result.receipt["client_session_id"])
        self.assertEqual(command[-1], "inspect the repository")
        # A receipt is metadata only; no policy content may reach runtime state.
        self.assertNotIn(b"always policy", (result.runtime_dir / "receipt.json").read_bytes())

    def test_a_failing_client_records_execution_ambiguous_and_blocks_the_task(self) -> None:
        self.returncode = 1
        with self._patches(), self._client_patch(), self._environment():
            with self.assertRaises(w2b1.AgentContextError) as failure:
                self._adapter().prepare_and_handoff_repositories(
                    workspace_root=self.root, repository_ids=("repo-a",), prompt="must not complete",
                )
        self.assertEqual(failure.exception.code, "E_CHANNEL")
        sessions = sorted((self.root / ".workspace/.runtime").iterdir())
        receipt = json.loads((sessions[-1] / "receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["state"], "EXECUTION_AMBIGUOUS")
        self.assertEqual(receipt["previous_state"], "SUBMISSION_STARTED")
        self.assertEqual(receipt["failure_code"], "E_CHANNEL")

    def test_a_different_reported_session_identity_never_claims_delivery(self) -> None:
        self.session_id = "11111111-2222-3333-4444-555555555555"
        with self._patches(), self._client_patch(), self._environment():
            with self.assertRaises(w2b1.AgentContextError) as failure:
                self._adapter().prepare_and_handoff_repositories(
                    workspace_root=self.root, repository_ids=("repo-a",), prompt="must not complete",
                )
        # A client that answers with another session identity is a lifecycle
        # failure, and the submission stays terminal rather than being retried.
        self.assertEqual(failure.exception.code, "E_LIFECYCLE")
        sessions = sorted((self.root / ".workspace/.runtime").iterdir())
        receipt = json.loads((sessions[-1] / "receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["state"], "EXECUTION_AMBIGUOUS")

    def test_source_drift_after_resolution_blocks_both_the_kernel_and_transport(self) -> None:
        with self._patches(), self._client_patch(), self._environment():
            launcher = self._adapter()
            resolution, preflight = launcher.resolve_repositories(
                workspace_root=self.root, repository_ids=("repo-a",),
            )
            transport = launcher._transport(preflight, resolution, "must not run", "s" * 8, None)
            (self.root / "CLAUDE.md").write_text("# changed after inspection\n", encoding="utf-8")
            with self.assertRaises(w2b1.AgentContextError) as transport_failure:
                transport.deliver(
                    payload=resolution.resolved.envelope_bytes,
                    envelope_sha256=resolution.resolved.envelope_sha256,
                    channel_id=resolution.channel_id,
                )
            with self.assertRaises(w2b1.AgentContextError) as kernel_failure:
                DeliveryKernel().prepare(launcher._delivery_request(
                    preflight, resolution, client_session_id="s" * 8,
                    launch_id="launch-fixture", authorization_trust_store=None,
                ))
        self.assertEqual(transport_failure.exception.code, "E_NATIVE_EVIDENCE")
        self.assertEqual(kernel_failure.exception.code, "E_SOURCE")
        self.assertEqual(self.commands, [])

    def test_the_transport_refuses_any_channel_step_12_4_has_not_wired(self) -> None:
        with self._patches(), self._client_patch(), self._environment():
            launcher = self._adapter()
            resolution, preflight = launcher.resolve_repositories(
                workspace_root=self.root, repository_ids=("repo-a",),
            )
            transport = launcher._transport(preflight, resolution, "must not run", "s" * 8, None)
            for channel in (adapter.HOOK_CHANNEL_ID, "claude-cli-stdin-prompt"):
                with self.subTest(channel=channel):
                    with self.assertRaises(w2b1.AgentContextError) as failure:
                        transport.deliver(
                            payload=resolution.resolved.envelope_bytes,
                            envelope_sha256=resolution.resolved.envelope_sha256,
                            channel_id=channel,
                        )
                    self.assertEqual(failure.exception.code, "E_CHANNEL")
        self.assertEqual(self.commands, [])

    def test_resume_continues_one_completed_generation_with_the_same_identity(self) -> None:
        kernel = DeliveryKernel()
        with self._patches(), self._client_patch(), self._environment():
            first = self._adapter().prepare_and_handoff_repositories(
                workspace_root=self.root, repository_ids=("repo-a",), prompt="first turn", kernel=kernel,
            )
            second = self._adapter().resume_and_handoff_repositories(
                workspace_root=self.root, runtime_dir=first.runtime_dir,
                repository_ids=("repo-a",), prompt="second turn", kernel=kernel,
            )
        self.assertEqual(second.receipt["state"], "COMPLETED")
        self.assertEqual(second.receipt["generation"], first.receipt["generation"] + 1)
        self.assertEqual(second.receipt["client_session_id"], first.receipt["client_session_id"])
        self.assertEqual(second.receipt["launch_id"], first.receipt["launch_id"])
        self.assertIn("--resume", self.commands[1])

    def test_a_fresh_launch_invalidates_the_named_prior_runtime(self) -> None:
        with self._patches(), self._client_patch(), self._environment():
            first = self._adapter().prepare_and_handoff_repositories(
                workspace_root=self.root, repository_ids=("repo-a",), prompt="first launch",
            )
            second = self._adapter().fresh_and_handoff_repositories(
                workspace_root=self.root, prior_runtime_dir=first.runtime_dir,
                repository_ids=("repo-a",), prompt="fresh launch",
            )
        self.assertFalse(first.runtime_dir.exists())
        self.assertEqual(second.receipt["generation"], 0)
        self.assertNotEqual(second.receipt["client_session_id"], first.receipt["client_session_id"])

    # ----------------------------------------------------------- authorization

    def test_a_mutating_task_cannot_be_selected_without_human_authorization(self) -> None:
        with self._patches(), self._client_patch(), self._environment():
            with self.assertRaises(w2b1.AgentContextError) as failure:
                self._adapter().prepare_and_handoff_repositories(
                    workspace_root=self.root, repository_ids=("repo-a",), tasks=("git-commit",),
                    operations=("git-commit",), prompt="must not start",
                )
        self.assertEqual(failure.exception.code, "E_AUTHORIZATION")
        self.assertEqual(self.commands, [])

    def test_a_canonical_launch_refuses_unverified_authorization_provenance(self) -> None:
        record = {
            "authorization_id": "human.commit", "kind": "explicit-user-message",
            "authorized_by": "fixture user", "source_ref": "conversation:fixture",
            "source_sha256": "a" * 64, "repositories": ["repo-a"], "operations": ["git-commit"],
            "issued_at": "2026-07-28T00:00:00Z",
        }
        with self._patches(), self._client_patch(), self._environment():
            with self.assertRaises(w2b1.AgentContextError) as failure:
                self._adapter(strict_trust_identity=True).resolve_repositories(
                    workspace_root=self.root, repository_ids=("repo-a",), tasks=("git-commit",),
                    operations=("git-commit",), authorizations=(record,),
                )
        self.assertEqual(failure.exception.code, "E_AUTHORIZATION")
        self.assertIn("externally verified", failure.exception.message)

    def test_adversarial_arguments_fail_before_any_evidence_is_read(self) -> None:
        for values, field in ((("../escape",), "repository"), (("repo-a", "repo-a"), "repository")):
            with self.subTest(values=values):
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    self._adapter().resolve_repositories(
                        workspace_root=self.root, repository_ids=values,
                    )
                self.assertEqual(failure.exception.code, "E_USAGE")
                self.assertIn(field, failure.exception.message)


class W12ClaudeLauncherTests(unittest.TestCase):
    """The CLI maps every fail-closed error onto its frozen exit code."""

    @staticmethod
    def _run(argv: list[str]) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = claude_repo_launcher.main(argv)
        return status, out.getvalue() + err.getvalue()

    def test_usage_and_stable_exit_codes_are_preserved(self) -> None:
        with mock.patch.object(claude_repo_launcher, "find_workspace_root") as discovery:
            discovery.side_effect = w2b1.AgentContextError(
                "E_SCOPE_UNAVAILABLE", "no canonical .m8-workspace-root ancestor exists"
            )
            status, output = self._run(["--repository", "repo-a", "prompt"])
        self.assertEqual(status, 5)
        self.assertIn("E_SCOPE_UNAVAILABLE", output)

    def test_request_preparation_never_redeems_a_capability(self) -> None:
        with mock.patch.object(claude_repo_launcher, "find_workspace_root", return_value=ROOT):
            status, output = self._run([
                "--repository", "fa-auth-m8", "--prepare-authorization-request", "prompt",
            ])
            self.assertEqual(status, 0)
            request = json.loads(output)
            self.assertEqual(request["repositories"], ["fa-auth-m8"])
            self.assertTrue(request["launch_id"].startswith("launch-"))
            rejected, _ = self._run([
                "--repository", "fa-auth-m8", "--prepare-authorization-request",
                "--authorization", "capability.json", "prompt",
            ])
        self.assertEqual(rejected, 2)


class W12ClaudeFrozenClassificationTests(unittest.TestCase):
    """The adapter reproduces the frozen Step 12.2 classification exactly."""

    def setUp(self) -> None:
        self.evidence = json.loads(NATIVE_EVIDENCE.read_text(encoding="utf-8"))
        self.scope = next(
            item for item in self.evidence["scopes"] if item["scope_id"] == "workspace-root"
        )
        configuration = self.evidence["configuration"]
        self.settings = {
            key: value for key, value in configuration.items() if key != "config_sha256"
        }
        self.load = self._recorded_load()

    def _recorded_load(self) -> native.ClaudeNativeLoad:
        """Rebuild the frozen root-scope capture from its own metadata."""
        text = _capture_text(ROOT, tuple(item["path"] for item in self.scope["native_sources"]))
        sources, external = native.parse_active_sources([text], ROOT)
        client = self.evidence["client"]
        return native.ClaudeNativeLoad(
            mechanism=native.MECHANISM, workspace_root=ROOT, project=".",
            client_identity=client["identity"], client_version=client["version"],
            client_sha256=client["sha256"], trust_state=self.scope["trust_state"],
            settings=self.settings, config_sha256=self.evidence["configuration"]["config_sha256"],
            captured_at=self.scope["captured_at"], sources=sources, external_labels=external,
            request_count=self.scope["request_count"],
            model_input_sha256=self.scope["model_input_sha256"],
            model_input_bytes=self.scope["model_input_bytes"], visible_text=text,
        )

    def _preflight(self) -> adapter.ClaudePreflight:
        client = self.evidence["client"]
        return adapter.ClaudePreflight(
            workspace_root=ROOT, launch_scope=ROOT, project=".",
            repositories=(ROOT / "fa-auth-m8",), repository_ids=("fa-auth-m8",),
            client_identity=client["identity"], client_version=client["version"],
            client_sha256=client["sha256"], settings=self.settings,
            config_sha256=self.load.config_sha256, trust_state="trusted",
            load=self.load, trust_identity={},
        )

    def test_the_selected_row_and_identities_match_the_frozen_record(self) -> None:
        frozen = next(
            item for item in self.evidence["classification"]
            if item["variant"] == "with-injected-child-instructions" and item["row_id"] == FULL_ROW
        )
        with mock.patch.object(
            adapter, "_reviewed_tree", lambda _root: dict(SYNTHETIC_TREE)
        ):
            resolution, _ = adapter.ClaudeLauncherAdapter(
                client_command="unused"
            ).resolve_repositories(
                workspace_root=ROOT, repository_ids=("fa-auth-m8",), preflight=self._preflight(),
            )
        self.assertEqual(resolution.capability.row_id, FULL_ROW)
        self.assertEqual(resolution.resolved.manifest["manifest_id"], frozen["manifest_id"])
        self.assertEqual(resolution.resolved.envelope_sha256, frozen["envelope_sha256"])
        self.assertEqual(resolution.native_evidence["native_evidence_id"], frozen["native_evidence_id"])
        self.assertEqual(
            [
                {
                    "path": entry["path"], "delivery": entry["delivery"],
                    "source_bytes": entry["source_bytes"],
                    "native_evidence_id": entry["native_evidence_id"],
                }
                for entry in resolution.resolved.manifest["entries"]
            ],
            frozen["entries"],
        )
        accounting = resolution.resolved.manifest["accounting"]
        for key, value in frozen["accounting"].items():
            self.assertEqual(accounting[key], value, key)
        # The frozen hook row overran its total, and the adapter records it.
        self.assertEqual([item["row_id"] for item in resolution.rejected_rows], [HOOK_ROW])
        self.assertIn("E_BUDGET", resolution.rejected_rows[0]["reason"])

    def test_the_thirty_three_absence_proofs_still_hold_for_this_launch(self) -> None:
        with mock.patch.object(
            adapter, "_reviewed_tree", lambda _root: dict(SYNTHETIC_TREE)
        ):
            resolution, _ = adapter.ClaudeLauncherAdapter(
                client_command="unused"
            ).resolve_repositories(
                workspace_root=ROOT, repository_ids=("fa-auth-m8",), preflight=self._preflight(),
            )
        self.assertEqual(
            [item["path"] for item in resolution.injection_evidence["sources"]],
            [item["path"] for item in self.evidence["proved_absent"]],
        )
        self.assertTrue(resolution.injection_evidence["exact_once_handoff_proven"])


class W12ClaudeAdapterEvidenceTests(unittest.TestCase):
    """The tracked Step 12.3 artifact must describe this exact tree."""

    def setUp(self) -> None:
        self.artifact = json.loads(ADAPTER_EVIDENCE.read_text(encoding="utf-8"))

    def test_artifacts_are_utf8_lf_and_final_newline_terminated(self) -> None:
        for path in (ADAPTER_EVIDENCE, ADAPTER_REPORT):
            raw = path.read_bytes()
            with self.subTest(path=path.name):
                raw.decode("utf-8", "strict")
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", raw)
                self.assertTrue(raw.endswith(b"\n"))

    def test_every_recorded_identity_recomputes_from_the_tracked_tree(self) -> None:
        for item in self.artifact["tooling"] + self.artifact["depends_on"]:
            path = item.get("path") or item["artifact"]
            with self.subTest(path=path):
                self.assertEqual(
                    item["sha256"], hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                )

    def test_the_matrix_names_only_tests_this_module_actually_defines(self) -> None:
        defined = set(dir(W12ClaudeAdapterFixtureTests))
        external = {"test_claude_client_settings_instruction_or_trust_drift_fails"}
        rows = self.artifact["fail_closed_matrix"]
        self.assertGreaterEqual(len(rows), 20)
        for row in rows:
            with self.subTest(stage=row["stage"]):
                self.assertIn(row["test"], defined | external)
                self.assertTrue(row["code"].startswith("E_"))

    def test_the_recorded_channel_policy_matches_the_adapter(self) -> None:
        policy = self.artifact["channel_policy"]
        self.assertEqual(tuple(policy["order"]), adapter.REQUIRED_ROW_IDS)
        self.assertIsNone(policy["hook_round_trip_evidence"])
        self.assertEqual(policy["hook_row_status"], "INELIGIBLE_UNTIL_12_4")
        self.assertEqual(
            self.artifact["lifecycle"]["states"],
            ["RESOLVED", "PREPARED", "SUBMISSION_STARTED", "COMPLETED", "EXECUTION_AMBIGUOUS", "FAILED"],
        )

    def test_the_frozen_reproduction_points_at_the_step_12_2_record(self) -> None:
        reproduction = self.artifact["frozen_reproduction"]
        evidence = json.loads(NATIVE_EVIDENCE.read_text(encoding="utf-8"))
        frozen = next(
            item for item in evidence["classification"]
            if item["variant"] == reproduction["variant"] and item["row_id"] == reproduction["row_id"]
        )
        for key in ("manifest_id", "envelope_sha256", "native_evidence_id"):
            self.assertEqual(reproduction[key], frozen[key], key)

    def test_the_driven_run_records_a_completed_metadata_only_receipt(self) -> None:
        run = self.artifact["driven_run"]
        self.assertEqual(run["delivery"]["state"], "COMPLETED")
        self.assertEqual(run["delivery"]["previous_state"], "SUBMISSION_STARTED")
        self.assertEqual(run["delivery"]["channel_id"], adapter.FULL_CONTENT_CHANNEL_ID)
        self.assertEqual(
            run["delivery"]["envelope_sha256"], run["delivery"]["transport_envelope_sha256"]
        )
        self.assertEqual(
            run["delivery"]["delivered_bytes"], run["delivery"]["transport_envelope_bytes"]
        )
        self.assertTrue(run["delivery"]["session_identity_matches"])
        self.assertTrue(run["delivery"]["runtime_dir_is_ignored"])
        self.assertEqual(run["preflight"]["registered_hook_events"], [])
        self.assertEqual(run["selection"]["row_id"], FULL_ROW)
        self.assertEqual(
            [item["row_id"] for item in run["selection"]["rejected_rows"]], [HOOK_ROW]
        )
        # The still-current native source and totals must match the live tree.
        source = run["preflight"]["native_sources"][0]
        self.assertEqual(
            source["source_sha256"], hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest()
        )
        accounting = run["selection"]["accounting"]
        self.assertLessEqual(accounting["model_visible_total"], accounting["effective_hard_limit"])


class W12ClaudeTrackedSourceTests(unittest.TestCase):
    """The step's own tracked sources stay portable and reviewed."""

    def test_new_tooling_is_utf8_lf_and_final_newline_terminated(self) -> None:
        for relative in (
            "scripts/agent_context/claude_delivery_adapter.py",
            "scripts/agent_context/claude_repo_launcher.py",
            "scripts/claude-repo.sh",
            "scripts/agent_context/tests/test_w12_claude_adapter.py",
        ):
            raw = (ROOT / relative).read_bytes()
            with self.subTest(path=relative):
                raw.decode("utf-8", "strict")
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", raw)
                self.assertTrue(raw.endswith(b"\n"))

    def test_the_wrapper_discovers_only_the_workspace_marker(self) -> None:
        wrapper = (ROOT / "scripts/claude-repo.sh").read_text(encoding="utf-8")
        self.assertIn("agent_context.claude_repo_launcher", wrapper)
        self.assertNotIn("git rev-parse", wrapper)
        self.assertTrue(os.access(ROOT / "scripts/claude-repo.sh", os.X_OK))

    def test_step_12_3_registers_no_hook_and_promotes_no_project_configuration(self) -> None:
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("hooks", settings)
        self.assertIsNone(adapter.HOOK_ROUND_TRIP_EVIDENCE)
        self.assertEqual(
            subprocess.run(
                ["git", "-C", str(ROOT), "check-ignore", "-q", ".workspace/.runtime"], check=False
            ).returncode,
            0,
        )


if __name__ == "__main__":
    unittest.main()
