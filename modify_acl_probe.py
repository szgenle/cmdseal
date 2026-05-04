#!/usr/bin/env python3
"""
modify_acl_probe — Observe whether keychain *modify* / *delete* calls
require interactive user auth (login password dialog) on items created
by cmdseal_helper with a strict SecAccessCreate ACL.

This probe informs Plan D (§5 of NEXT.md): if modify/delete is silent,
then `cmdseal rotate` can be fully non-interactive. If it times out
(= macOS popped a GUI password dialog that nobody clicks), `rotate`
must explicitly warn the user.

Non-interactive rule (same as acl_test.py):
  - every subprocess runs with a hard 5s timeout
  - < 1s exit 0 ............. operation went through silently
  - timeout .................. a GUI prompt was triggered
  - non-zero exit ............ OS refused via ACL / missing item

USAGE:
    # Pre-req: cmdseal_helper has been built under _build/ (same build
    # as acl_test.py assumes). Any existing sealed binary path works
    # as the "trusted app" for ACL setup — by default we reuse
    # ./demo_sealed if it exists, else any file path passed via
    # --trusted.
    python3 modify_acl_probe.py [--trusted /path/to/signed/bin]

WHAT IT DOES:
    For each scenario, creates a fresh keychain item bound to the
    trusted binary's cdhash, then exercises the target operation and
    measures the outcome.

    scenarios:
      1. helper delete   (caller NOT in ACL trusted-apps)
      2. helper update   (caller NOT in ACL trusted-apps)
      3. /usr/bin/security delete-generic-password
      4. /usr/bin/security add -U     (update via replace)

At the end prints a decision table that tells you which rotate path
is viable.
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE   = Path(__file__).resolve().parent
HELPER = HERE / "_build" / "cmdseal_helper"
DEFAULT_TRUSTED = HERE / "demo_sealed"

SILENT = "silent"      # exit 0 within 1s
PROMPTED = "prompted"  # timeout -> GUI dialog
REFUSED = "refused"    # non-zero exit, no timeout
UNKNOWN = "unknown"


def _classify(rc: int, elapsed: float, timed_out: bool) -> str:
    if timed_out:
        return PROMPTED
    if rc == 0 and elapsed < 1.0:
        return SILENT
    if rc != 0:
        return REFUSED
    return UNKNOWN


def run(cmd: list[str], stdin: str | None = None, timeout: float = 5.0):
    t0 = time.time()
    try:
        r = subprocess.run(
            cmd, input=stdin, capture_output=True, text=True,
            timeout=timeout,
        )
        dt = time.time() - t0
        verdict = _classify(r.returncode, dt, False)
        return verdict, r.returncode, dt, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        return PROMPTED, -1, dt, "", "(timeout)"


def print_case(title: str, verdict, rc, dt, out, err):
    print(f"\n=== {title} ===")
    print(f"  verdict : {verdict}")
    print(f"  exit    : {rc}   time: {dt:.2f}s")
    if out.strip():
        print(f"  stdout  : {out.strip()[:200]!r}")
    if err.strip():
        print(f"  stderr  : {err.strip()[:200]!r}")


def seed_item(service: str, account: str, password: str,
              trusted: Path) -> bool:
    """Creates a fresh keychain item with strict ACL bound to
    `trusted`. Any previous item with the same (service, account) is
    replaced by cmdseal_helper.add internally."""
    r = subprocess.run(
        [str(HELPER), "add", service, account, str(trusted)],
        input=password, capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        print(f"[seed] helper add failed rc={r.returncode}")
        print(f"       stderr: {r.stderr.strip()[:300]!r}")
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trusted", type=Path, default=DEFAULT_TRUSTED,
                    help="signed binary to use as ACL trusted app "
                         "(default: ./demo_sealed)")
    args = ap.parse_args()

    if not HELPER.exists():
        print(f"ERROR: helper not found at {HELPER}")
        print("       build it: cc -O2 -Wno-deprecated-declarations "
              "-o _build/cmdseal_helper cmdseal_helper.c "
              "-framework Security -framework CoreFoundation "
              "&& codesign -s - _build/cmdseal_helper")
        return 2
    if not args.trusted.exists():
        print(f"ERROR: trusted binary not found at {args.trusted}")
        print("       run the v1 PoC first so demo_sealed exists, "
              "or pass --trusted /path/to/signed/bin")
        return 2

    # Use a unique service-per-run so previous test leftovers don't
    # interfere. Account stays stable so user can clean up by hand.
    tag = uuid.uuid4().hex[:8]
    service = f"cmdseal.probe.{tag}"
    account = "probe"
    seed_pw = "initial-secret-topsecret42"
    new_pw  = "rotated-secret-topsecret42"

    print(f"probe service : {service}")
    print(f"probe account : {account}")
    print(f"trusted app   : {args.trusted}")

    results: dict[str, str] = {}

    # --- Case 1: helper delete (helper NOT in trusted-apps) ---
    if not seed_item(service, account, seed_pw, args.trusted):
        return 3
    v, rc, dt, out, err = run(
        [str(HELPER), "delete", service, account])
    print_case("1. helper delete (caller outside ACL trusted-apps)",
               v, rc, dt, out, err)
    results["helper_delete"] = v

    # --- Case 2: helper update (helper NOT in trusted-apps) ---
    if not seed_item(service, account, seed_pw, args.trusted):
        return 3
    v, rc, dt, out, err = run(
        [str(HELPER), "update", service, account],
        stdin=new_pw)
    print_case("2. helper update (caller outside ACL trusted-apps)",
               v, rc, dt, out, err)
    results["helper_update"] = v

    # --- Case 3: /usr/bin/security delete ---
    if not seed_item(service, account, seed_pw, args.trusted):
        return 3
    v, rc, dt, out, err = run(
        ["/usr/bin/security", "delete-generic-password",
         "-s", service, "-a", account])
    print_case("3. security(1) delete-generic-password",
               v, rc, dt, out, err)
    results["security_delete"] = v

    # --- Case 4: /usr/bin/security add -U (update via replace) ---
    if not seed_item(service, account, seed_pw, args.trusted):
        return 3
    v, rc, dt, out, err = run(
        ["/usr/bin/security", "add-generic-password",
         "-U", "-s", service, "-a", account, "-w", new_pw])
    print_case("4. security(1) add -U (update via replace)",
               v, rc, dt, out, err)
    results["security_update"] = v

    # --- final cleanup (best effort, ignore outcome) ---
    subprocess.run(
        ["/usr/bin/security", "delete-generic-password",
         "-s", service, "-a", account],
        capture_output=True, timeout=5,
    )

    # --- Decision summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for k, v in results.items():
        print(f"  {k:20s} : {v}")

    print("\nInterpretation for Plan D's `cmdseal rotate`:")
    hd = results["helper_delete"]
    hu = results["helper_update"]
    if hd == SILENT and hu == SILENT:
        print("  ✅ FULL NON-INTERACTIVE: helper can delete/modify without")
        print("     GUI prompt. rotate can be scripted end-to-end.")
    elif hd == PROMPTED or hu == PROMPTED:
        print("  ⚠️  GUI PROMPT REQUIRED for modify/delete.")
        print("     `cmdseal rotate` must warn the user that macOS will")
        print("     ask for the login password. Consider adding helper")
        print("     cdhash to modify-ACL via SecAccessCreate's ACL list.")
    else:
        print("  ❓ UNEXPECTED outcome — inspect per-case verdicts above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
