"""Cross-repository authorization conformance runner (§6, ``TEST-CROSS-01``).

Entry point for the Phase 5 *"Run local-package matrix in dependency order and
prove issuer/consumer parity"* bullet. It:

1. resolves the SDK -> fastapi -> issuer/examples local-package matrix in
   dependency order and asserts each resolves to the intended workspace
   version;
2. loads the SDK-owned checksum-verified fixture matrix (``FIXTURE-01``) — the
   loader itself fails closed on schema-version drift or a checksum mismatch;
3. proves issuer/consumer decision parity for every valid and invalid claim
   combination, plus the concurrent-login-during-downgrade generation race and
   the durable-outbox propagation.

Exit code is ``0`` only when every check passes; any failure (or an import that
does not resolve in-workspace) exits non-zero, fail-closed.

Run from the workspace root against an environment where the local platform
packages are installed::

    python -m scripts.conformance.run_conformance
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from scripts.conformance import CheckResult


def _print_section(title: str, results: Sequence[CheckResult]) -> bool:
    print(f"\n=== {title} ===")
    ok = True
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"  [{marker}] {result.name}: {result.detail}")
        ok = ok and result.passed
    return ok


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print only the final summary line",
    )
    args = parser.parse_args(argv)

    # Imported lazily so a missing/misresolved platform package surfaces as a
    # clean conformance failure rather than a module-load crash.
    from auth_sdk_m8.testing import load_authorization_fixture_matrix

    from scripts.conformance.api_key_principal_conformance import (
        run_api_key_conformance,
    )
    from scripts.conformance.issuer_consumer_parity import run_parity_matrix
    from scripts.conformance.local_package_matrix import resolve_local_package_matrix

    sections: list[tuple[str, list[CheckResult]]] = []
    matrix_results = resolve_local_package_matrix()
    sections.append(("Local-package matrix (dependency order)", matrix_results))

    # The loader verifies schema version + checksum; a mismatch raises here and
    # is reported as a fail-closed error rather than a silent local expectation.
    fixture_matrix = load_authorization_fixture_matrix()
    sections.append(("Issuer/consumer parity", run_parity_matrix(fixture_matrix)))
    sections.append(
        (
            "API-key principal conformance (§3.12)",
            run_api_key_conformance(fixture_matrix),
        )
    )

    all_ok = True
    total = 0
    failed = 0
    for title, results in sections:
        total += len(results)
        failed += sum(1 for r in results if not r.passed)
        if args.quiet:
            all_ok = all_ok and all(r.passed for r in results)
        else:
            all_ok = _print_section(title, results) and all_ok

    passed = total - failed
    print(
        f"\nConformance summary: {passed}/{total} checks passed "
        f"({'GREEN' if all_ok else 'RED'})"
    )
    return 0 if all_ok else 1


def main() -> None:  # pragma: no cover - thin CLI wrapper
    sys.exit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
