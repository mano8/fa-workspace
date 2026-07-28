"""Step 12.5 Claude-mode fixtures and adversarial coverage.

Steps 12.1-12.4 froze the capability matrix, the native-load evidence
mechanism, the fail-closed adapter, and the byte-exact delivery channel. This
module adds the cross-cutting proofs the addendum's resolved-context delivery
contract requires but the earlier per-step suites did not yet cover together:

* the adapter's resolved manifest/envelope for a real registered repository —
  ``fa-auth-m8`` and one multi-facet peer, ``media-service-m8`` — is exactly
  what an independent call to the resolver produces for the same captured
  request, and a completed receipt's identities equal that resolution
  byte-for-byte;
* the frozen interactive and non-interactive capability rows still measure the
  identical verified boundary, and the resolver itself — not just the
  adapter — refuses an ``OPTIONAL`` interactive row as canonical;
* a ``SessionStart`` firing, followed by the first ``UserPromptSubmit``
  prompt and a second one in the same generation, delivers the envelope
  exactly once;
* a source that drifts after a generation completes invalidates resume before
  any further client invocation;
* marker-only workspace discovery finds the root from a nested repository
  directory (parent-found) and fails closed with no evidence or client use
  when no marker exists anywhere in the ancestry (parent-absent standalone);
  and
* the generic runtime-security and concurrency policy — unpredictable session
  directories, owner-only permissions, reparse rejection, and safe cleanup
  after interruption — protects Claude's own runtime state and channel
  artifacts exactly as it protects every other delivery.

These tests are offline. They reuse the Step 12.3 fixture workspace
(``W12ClaudeAdapterFixtureTests``) and the Step 12.4 armed-runtime harness
(``ArmedRuntime``) by composition rather than forking them, and the two
live-tree classes read only the real, already-tracked evidence and repository
files; neither invokes a client process or contacts a vendor API.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_context import claude_delivery_adapter as adapter
from agent_context import claude_hook_gate as hook_gate
from agent_context import w2b1
from agent_context.delivery_kernel import DeliveryKernel
from agent_context.resolve_context import ResolutionRequest, resolve_context
from agent_context.tests import test_w12_claude_adapter as _adapter_fixtures
from agent_context.tests.test_w12_claude_adapter import CAPABILITY, ROOT, _load
from agent_context.tests.test_w12_claude_hook_channel import ArmedRuntime


# media-service-m8 shares kind/layer and three of four facets with
# fa-auth-m8 (python/service/api-service/fastapi) but diverges on its domain
# facet (media vs auth-security), so the two repositories exercise a
# genuinely different policy slice on the identical live tree.
MULTI_FACET_PEER = "media-service-m8"
SYNTHETIC_TREE = {"algorithm": "git-sha1", "value": "b" * 40}
INTERACTIVE_ROW_PAIRS = (
    ("claude-devcontainer-non-interactive-hook-additional-context",
     "claude-devcontainer-interactive-hook-additional-context"),
    ("claude-devcontainer-non-interactive-append-system-prompt",
     "claude-devcontainer-interactive-append-system-prompt"),
)


def _fixture() -> _adapter_fixtures.W12ClaudeAdapterFixtureTests:
    fixture = _adapter_fixtures.W12ClaudeAdapterFixtureTests()
    fixture.setUp()
    return fixture


class W12ClaudeLiveTreeResolverParityTests(unittest.TestCase):
    """The adapter's resolution equals an independent resolver call exactly.

    Both repositories are launched at root scope, so only the workspace root
    ``CLAUDE.md`` is native and every child instruction file is proved absent
    and injected, exactly as Step 12.2 measured for ``fa-auth-m8``.
    """

    def _preflight(self, repository_id: str) -> adapter.ClaudePreflight:
        client = json.loads(CAPABILITY.read_text(encoding="utf-8"))["client"]
        load = _load(
            ROOT, ("CLAUDE.md",), client_identity=client["resolved_path"],
            client_version=client["version"], client_sha256=client["sha256"],
        )
        return adapter.ClaudePreflight(
            workspace_root=ROOT, launch_scope=ROOT, project=".",
            repositories=(ROOT / repository_id,), repository_ids=(repository_id,),
            client_identity=client["resolved_path"], client_version=client["version"],
            client_sha256=client["sha256"], settings=load.settings,
            config_sha256=load.config_sha256, trust_state="trusted",
            load=load, trust_identity={},
        )

    def _resolve(self, repository_id: str) -> tuple[adapter.ClaudeResolution, ResolutionRequest]:
        """Drive one live resolution and capture the exact request it built."""
        original = adapter.resolve_context
        calls: list[ResolutionRequest] = []

        def _spy(request: ResolutionRequest):
            calls.append(request)
            return original(request)

        with mock.patch.object(
            adapter, "_reviewed_tree", lambda _root: dict(SYNTHETIC_TREE)
        ), mock.patch.object(adapter, "resolve_context", side_effect=_spy):
            resolution, _ = adapter.ClaudeLauncherAdapter(
                client_command="unused"
            ).resolve_repositories(
                workspace_root=ROOT, repository_ids=(repository_id,),
                preflight=self._preflight(repository_id),
            )
        selected = next(
            call for call in calls if call.capability_row["channel_id"] == resolution.channel_id
        )
        return resolution, selected

    def _assert_byte_for_byte_parity(self, repository_id: str) -> None:
        resolution, request = self._resolve(repository_id)
        independent = resolve_context(request)
        self.assertEqual(independent.manifest, resolution.resolved.manifest)
        self.assertEqual(independent.envelope, resolution.resolved.envelope)
        self.assertEqual(independent.envelope_bytes, resolution.resolved.envelope_bytes)
        self.assertEqual(independent.envelope_sha256, resolution.resolved.envelope_sha256)
        # The resolver is a pure function of its explicit inputs: a second
        # independent call is exactly as deterministic as the first.
        again = resolve_context(request)
        self.assertEqual(again.envelope_bytes, resolution.resolved.envelope_bytes)
        self.assertEqual(again.manifest["manifest_id"], resolution.resolved.manifest["manifest_id"])

    def test_fa_auth_m8_resolution_matches_an_independent_resolver_call(self) -> None:
        self._assert_byte_for_byte_parity("fa-auth-m8")

    def test_a_multi_facet_peer_resolution_matches_an_independent_resolver_call(self) -> None:
        self._assert_byte_for_byte_parity(MULTI_FACET_PEER)

    def test_the_two_repositories_resolve_to_distinct_manifests_and_entries(self) -> None:
        first, _ = self._resolve("fa-auth-m8")
        second, _ = self._resolve(MULTI_FACET_PEER)
        self.assertNotEqual(
            first.resolved.manifest["manifest_id"], second.resolved.manifest["manifest_id"]
        )
        self.assertNotEqual(first.resolved.envelope_sha256, second.resolved.envelope_sha256)
        first_paths = {entry["path"] for entry in first.resolved.manifest["entries"]}
        second_paths = {entry["path"] for entry in second.resolved.manifest["entries"]}
        self.assertIn("fa-auth-m8/CLAUDE.md", first_paths)
        self.assertIn(f"{MULTI_FACET_PEER}/CLAUDE.md", second_paths)
        self.assertNotIn(f"{MULTI_FACET_PEER}/CLAUDE.md", first_paths)


class W12ClaudeChannelModeParityTests(unittest.TestCase):
    """Interactive and non-interactive rows share one verified boundary.

    Step 12.1 measured identical byte fixtures for both modes; only the two
    non-interactive rows are ``REQUIRED`` and wired. This proves the frozen
    matrix still agrees and that the resolver itself — not merely the
    adapter's row selection — refuses an ``OPTIONAL`` interactive row.
    """

    def setUp(self) -> None:
        self.artifact = json.loads(CAPABILITY.read_text(encoding="utf-8"))
        self.rows = {item["row_id"]: item["capability_row"] for item in self.artifact["rows"]}

    @staticmethod
    def _effective_hard_limit(row: dict) -> int:
        return min(
            32768, row["verified_channel_limit"],
            row["client_context_allowance"] - row["reserved_margin"],
        )

    def test_the_effective_hard_limit_is_identical_across_modes(self) -> None:
        for non_interactive_id, interactive_id in INTERACTIVE_ROW_PAIRS:
            with self.subTest(rows=(non_interactive_id, interactive_id)):
                non_interactive = self.rows[non_interactive_id]
                interactive = self.rows[interactive_id]
                self.assertEqual(non_interactive["status"], "REQUIRED")
                self.assertEqual(interactive["status"], "OPTIONAL")
                self.assertEqual(non_interactive["channel_id"], interactive["channel_id"])
                self.assertEqual(non_interactive["inspection_mechanism"], interactive["inspection_mechanism"])
                self.assertEqual(
                    self._effective_hard_limit(non_interactive),
                    self._effective_hard_limit(interactive),
                )

    def test_only_the_non_interactive_rows_are_the_wired_required_set(self) -> None:
        self.assertEqual(set(adapter.REQUIRED_ROW_IDS), {pair[0] for pair in INTERACTIVE_ROW_PAIRS})

    def test_an_interactive_row_is_refused_by_the_resolver_itself(self) -> None:
        registry = json.loads((ROOT / ".workspace/repo-types.json").read_text(encoding="utf-8"))
        policy_index = json.loads((ROOT / ".workspace/policy.index.json").read_text(encoding="utf-8"))
        policy_metadata = json.loads((ROOT / ".workspace/policy.metadata.json").read_text(encoding="utf-8"))
        for _, interactive_row_id in INTERACTIVE_ROW_PAIRS:
            with self.subTest(row_id=interactive_row_id):
                row = self.rows[interactive_row_id]
                with self.assertRaises(w2b1.AgentContextError) as failure:
                    resolve_context(ResolutionRequest(
                        root=ROOT, registry=registry, policy_index=policy_index,
                        policy_metadata=policy_metadata, capability_row=row,
                        reviewed_tree=dict(SYNTHETIC_TREE), agent="claude",
                        platform=row["platform"], mode=row["mode"],
                        repositories=("fa-auth-m8",),
                    ))
                self.assertEqual(failure.exception.code, "E_UNSUPPORTED_MODE")


class W12ClaudeReceiptResolverParityTests(unittest.TestCase):
    """A completed receipt's identities equal the resolver output exactly."""

    def setUp(self) -> None:
        self.fixture = _fixture()
        # Force the always-available full-content row so this class proves
        # receipt/resolver parity directly from one CLI argument rather than
        # re-deriving the Step 12.4 hook round trip, which that step's own
        # suite already covers byte-for-byte.
        self._force_full_content = mock.patch.object(adapter, "HOOK_ROUND_TRIP_EVIDENCE", None)
        self._force_full_content.start()

    def tearDown(self) -> None:
        self._force_full_content.stop()
        self.fixture.tearDown()

    def test_the_completed_receipt_matches_the_resolved_envelope_byte_for_byte(self) -> None:
        f = self.fixture
        resolution, _ = f._resolve()
        with f._patches(), f._client_patch(), f._environment():
            result = f._adapter().prepare_and_handoff_repositories(
                workspace_root=f.root, repository_ids=("repo-a",), prompt="parity check",
            )
        self.assertEqual(result.receipt["manifest_id"], resolution.resolved.manifest["manifest_id"])
        self.assertEqual(result.receipt["envelope_sha256"], resolution.resolved.envelope_sha256)
        self.assertEqual(result.receipt["delivered_bytes"], len(resolution.resolved.envelope_bytes))
        self.assertEqual(list(result.session["sources"]), list(resolution.resolved.manifest["entries"]))
        command = f.commands[-1]
        self.assertIn("--append-system-prompt", command)
        delivered = command[command.index("--append-system-prompt") + 1].encode("utf-8")
        self.assertEqual(delivered, resolution.resolved.envelope_bytes)

    def test_session_transitions_follow_the_exact_contractual_lifecycle(self) -> None:
        f = self.fixture
        with f._patches(), f._client_patch(), f._environment():
            first = f._adapter().prepare_and_handoff_repositories(
                workspace_root=f.root, repository_ids=("repo-a",), prompt="first turn",
            )
            second = f._adapter().resume_and_handoff_repositories(
                workspace_root=f.root, runtime_dir=first.runtime_dir,
                repository_ids=("repo-a",), prompt="second turn",
            )
        names = sorted(
            child.name for child in first.runtime_dir.iterdir() if child.name.startswith("journal-")
        )
        states = [
            json.loads((first.runtime_dir / name).read_text(encoding="utf-8"))["receipt"]["state"]
            for name in names
        ]
        self.assertEqual(
            states,
            ["RESOLVED", "PREPARED", "SUBMISSION_STARTED", "COMPLETED",
             "RESOLVED", "PREPARED", "SUBMISSION_STARTED", "COMPLETED"],
        )
        self.assertEqual(second.receipt["generation"], first.receipt["generation"] + 1)
        self.assertEqual(second.receipt["client_session_id"], first.receipt["client_session_id"])


class W12ClaudeDuplicateInjectionSequenceTests(unittest.TestCase):
    """SessionStart-plus-first-prompt never yields two copies of one envelope.

    Step 12.1 measured that ``SessionStart`` carries ``additionalContext``
    with the same boundary as ``UserPromptSubmit``, and Step 12.4's own claim
    check proved the *count*, not the presence, of a claim is the exactly-once
    evidence. This drives that exact sequence — a ``SessionStart`` firing,
    the first ``UserPromptSubmit`` prompt, and a second one in the same
    generation — end to end against the gate.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.armed = ArmedRuntime(self.base)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_session_start_then_the_first_and_a_second_prompt_deliver_exactly_once(self) -> None:
        self.armed.arm()
        with self.assertRaises(w2b1.AgentContextError) as failure:
            hook_gate.gate(
                runtime_dir=self.armed.runtime_dir,
                payload=self.armed.payload(hook_event_name="SessionStart"),
            )
        self.assertEqual(failure.exception.code, "E_CHANNEL")
        self.assertEqual(self.armed.claims(), [])
        first_prompt = hook_gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        self.assertIn("additionalContext", first_prompt["hookSpecificOutput"])
        self.assertEqual(self.armed.claims(), ["channel-claim-000000.json"])
        second_prompt = hook_gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        self.assertNotIn("additionalContext", second_prompt["hookSpecificOutput"])
        # SessionStart contributed nothing, the first prompt claimed exactly
        # once, and the second prompt reused that same claim rather than
        # creating a second one.
        self.assertEqual(self.armed.claims(), ["channel-claim-000000.json"])

    def test_a_resumed_generation_repeats_the_same_session_start_refusal(self) -> None:
        """The refusal is not a one-time bootstrap fluke; every generation repeats it."""
        self.armed.arm()
        hook_gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        # A resumed launch arms the same session directory for generation one.
        self.armed.generation = 1
        self.armed.arm()
        with self.assertRaises(w2b1.AgentContextError) as failure:
            hook_gate.gate(
                runtime_dir=self.armed.runtime_dir,
                payload=self.armed.payload(hook_event_name="SessionStart"),
            )
        self.assertEqual(failure.exception.code, "E_CHANNEL")
        hook_gate.gate(runtime_dir=self.armed.runtime_dir, payload=self.armed.payload())
        self.assertEqual(
            self.armed.claims(), ["channel-claim-000000.json", "channel-claim-000001.json"]
        )


class W12ClaudeResumeSourceDriftTests(unittest.TestCase):
    """A source that drifts after completion invalidates resume, not silently."""

    def setUp(self) -> None:
        self.fixture = _fixture()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_a_source_changed_after_completion_invalidates_resume_reuse(self) -> None:
        cases = (
            (lambda: (self.fixture.root / ".workspace" / "policies" / "always.md").write_text(
                "always policy drifted\n", encoding="utf-8"
            ), "injected policy source"),
            (lambda: (self.fixture.root / "CLAUDE.md").write_text(
                "# drifted after completion\n", encoding="utf-8"
            ), "native workspace source"),
        )
        for mutate, label in cases:
            with self.subTest(source=label):
                self.tearDown()
                self.fixture = _fixture()
                f = self.fixture
                with f._patches(), f._client_patch(), f._environment():
                    first = f._adapter().prepare_and_handoff_repositories(
                        workspace_root=f.root, repository_ids=("repo-a",), prompt="first turn",
                    )
                self.assertEqual(len(f.commands), 1)
                mutate()
                with f._patches(), f._client_patch(), f._environment():
                    with self.assertRaises(w2b1.AgentContextError) as failure:
                        f._adapter().resume_and_handoff_repositories(
                            workspace_root=f.root, runtime_dir=first.runtime_dir,
                            repository_ids=("repo-a",), prompt="second turn",
                        )
                # A source change yields a different manifest identity than
                # the prior completed generation, so resume's own linkage
                # check — not a silent rebuild under the old manifest — is
                # what blocks reuse, exactly as the delivery contract requires.
                self.assertEqual(failure.exception.code, "E_RECEIPT")
                self.assertEqual(len(f.commands), 1)
                receipt = json.loads((first.runtime_dir / "receipt.json").read_text(encoding="utf-8"))
                self.assertEqual(receipt["state"], "COMPLETED")


class W12ClaudeStandaloneScopeTests(unittest.TestCase):
    """Marker-only discovery: parent-found from a nested start, parent-absent fails closed."""

    def setUp(self) -> None:
        self.fixture = _fixture()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_parent_found_discovery_walks_up_from_a_nested_directory(self) -> None:
        f = self.fixture
        nested = f.child / "nested" / "deeper"
        nested.mkdir(parents=True)
        self.assertEqual(adapter.find_workspace_root(nested), f.root)
        self.assertEqual(adapter.find_workspace_root(f.child), f.root)
        self.assertEqual(adapter.find_workspace_root(f.root), f.root)

    def test_parent_absent_standalone_fails_closed_before_any_evidence_or_client_use(self) -> None:
        f = self.fixture
        with tempfile.TemporaryDirectory() as standalone:
            orphan = Path(standalone).resolve()
            with self.assertRaises(w2b1.AgentContextError) as discovery_failure:
                adapter.find_workspace_root(orphan)
            self.assertEqual(discovery_failure.exception.code, "E_SCOPE_UNAVAILABLE")
            self.assertIn(".m8-workspace-root", discovery_failure.exception.message)
            with f._patches(), f._client_patch(), f._environment():
                with self.assertRaises(w2b1.AgentContextError) as preflight_failure:
                    f._adapter().preflight(workspace_root=orphan, repository_ids=("repo-a",))
            self.assertEqual(preflight_failure.exception.code, "E_SCOPE_UNAVAILABLE")
        # Discovery fails before any capability, trust, or native evidence is
        # ever read, so no client command is ever built for an absent parent.
        self.assertEqual(f.commands, [])


class W12ClaudeRuntimeSecurityReuseTests(unittest.TestCase):
    """The generic runtime-security/concurrency policy protects Claude state too."""

    def setUp(self) -> None:
        self.fixture = _fixture()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_runtime_session_directory_names_are_unpredictable(self) -> None:
        kernel = DeliveryKernel()
        names = [kernel._new_runtime_dir(self.fixture.root).name for _ in range(16)]
        for name in names:
            self.assertRegex(name, r"^session-[0-9a-f]{48}$")
        self.assertEqual(len(set(names)), len(names))
        # 48 hex characters of secrets.token_hex(24) is 192 bits of entropy;
        # creation order and lexicographic order agreeing by chance is
        # astronomically unlikely for 16 independent draws.
        self.assertNotEqual(names, sorted(names))

    def test_a_completed_claude_generation_leaves_only_owner_only_flat_state(self) -> None:
        f = self.fixture
        with f._patches(), f._client_patch(), f._environment():
            result = f._adapter().prepare_and_handoff_repositories(
                workspace_root=f.root, repository_ids=("repo-a",), prompt="permissions",
            )
        self.assertGreater(len(list(result.runtime_dir.iterdir())), 0)
        for entry in result.runtime_dir.iterdir():
            info = entry.lstat()
            with self.subTest(entry=entry.name):
                self.assertFalse(stat.S_ISLNK(info.st_mode))
                self.assertTrue(stat.S_ISREG(info.st_mode))
                if os.name == "posix":
                    self.assertEqual(info.st_uid, os.getuid())
                    self.assertEqual(stat.S_IMODE(info.st_mode) & 0o077, 0)
        self.assertEqual(result.runtime_dir.stat().st_mode & 0o777, 0o700)

    def test_a_symlinked_runtime_directory_is_never_resumed(self) -> None:
        f = self.fixture
        with f._patches(), f._client_patch(), f._environment():
            first = f._adapter().prepare_and_handoff_repositories(
                workspace_root=f.root, repository_ids=("repo-a",), prompt="one",
            )
        real = first.runtime_dir
        decoy = f.base / "decoy"
        decoy.mkdir(mode=0o700)
        shutil.rmtree(real)
        real.symlink_to(decoy)
        with f._patches(), f._client_patch(), f._environment():
            with self.assertRaises(w2b1.AgentContextError) as failure:
                f._adapter().resume_and_handoff_repositories(
                    workspace_root=f.root, runtime_dir=real,
                    repository_ids=("repo-a",), prompt="resume onto a reparsed path",
                )
        self.assertEqual(failure.exception.code, "E_RUNTIME")
        # The first, real handoff is the only client invocation that ever ran.
        self.assertEqual(len(f.commands), 1)

    def test_an_interrupted_claude_handoff_still_cleans_up_safely(self) -> None:
        f = self.fixture

        def _fault(boundary: str) -> None:
            if boundary == "after-transport":
                raise RuntimeError("simulated interruption")

        kernel = DeliveryKernel(fault_hook=_fault)
        with f._patches(), f._client_patch(), f._environment():
            with self.assertRaises(w2b1.AgentContextError) as failure:
                f._adapter().prepare_and_handoff_repositories(
                    workspace_root=f.root, repository_ids=("repo-a",),
                    prompt="interrupted", kernel=kernel,
                )
        self.assertEqual(failure.exception.code, "E_CHANNEL")
        sessions = sorted((f.root / ".workspace" / ".runtime").iterdir())
        runtime_dir = sessions[-1]
        receipt = json.loads((runtime_dir / "receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["state"], "EXECUTION_AMBIGUOUS")
        # The generic policy already covers whatever Claude-specific
        # channel-* artifacts the interrupted generation armed; cleanup needs
        # no Claude-specific carve-out to remove them safely.
        DeliveryKernel().cleanup(runtime_dir, f.root)
        self.assertFalse(runtime_dir.exists())


if __name__ == "__main__":
    unittest.main()
