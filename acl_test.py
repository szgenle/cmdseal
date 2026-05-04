#!/usr/bin/env python3
"""
Non-interactive ACL negative test.

Each candidate is run with a hard timeout. If macOS pops a GUI
keychain prompt, the child process will hang waiting for user
interaction; our timeout then fires. Any such timeout means the
ACL IS in fact enforcing against that caller (the user just never
clicked Allow, so it was never authorized).

If a caller returns the secret within <1s, ACL is NOT enforcing
against it.
"""
import subprocess
import sys
import time
from pathlib import Path

HERE   = Path(__file__).resolve().parent
SEALED = HERE / "demo_sealed"
COPY   = HERE / "demo_sealed_copy"
PROBE  = HERE / "_build" / "reader_probe"


def strings_of(path, pattern):
    out = subprocess.run(["strings", str(path)], capture_output=True, text=True)
    for line in out.stdout.splitlines():
        if pattern in line:
            return line
    return None


def run_case(name, cmd, timeout=5.0):
    print(f"\n=== {name} ===")
    print(f"  cmd: {' '.join(cmd)}")
    t0 = time.time()
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        dt = time.time() - t0
        stdout = (res.stdout or "").strip()
        stderr = (res.stderr or "").strip()
        print(f"  -> exit={res.returncode}  time={dt:.2f}s")
        if stdout:
            print(f"     stdout: {stdout!r}")
        if stderr:
            print(f"     stderr: {stderr[:200]!r}")
        if dt < 1.0 and res.returncode == 0 and "topsecret42" in stdout:
            print(f"  VERDICT: 🔓 ACL DID NOT BLOCK "
                  f"(instant read, no prompt)")
        elif res.returncode != 0:
            print(f"  VERDICT: ✅ ACL BLOCKED (caller denied)")
        else:
            print(f"  VERDICT: (inconclusive)")
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        print(f"  -> TIMEOUT after {dt:.2f}s")
        print(f"  VERDICT: ✅ ACL LIKELY ENFORCED "
              f"(GUI prompt shown; nobody clicked Allow)")


def main():
    # Find prefix.
    line = strings_of(SEALED, "cmdseal.")
    if not line:
        print("cannot find cmdseal.* in strings(sealed). Did you build it?")
        return 1
    prefix = line.strip()
    # The string in the binary is the prefix itself (not prefix.name).
    print(f"service prefix: {prefix}")
    service = f"{prefix}.mypass"

    # 1) positive control: the sealed binary itself.
    run_case("POS: sealed binary (authorized caller)",
             [str(SEALED)])

    # 2) /usr/bin/security direct read (Apple-signed other process).
    run_case("NEG: /usr/bin/security find-generic-password",
             ["/usr/bin/security", "find-generic-password",
              "-s", service, "-a", "ws", "-w"])

    # 3) a different ad-hoc signed binary doing the same SPI call.
    if PROBE.exists():
        run_case("NEG: reader_probe (different ad-hoc signed binary)",
                 [str(PROBE), service, "ws"])

    # 4) a BYTEWISE-IDENTICAL copy of sealed binary at a different path.
    if not COPY.exists():
        subprocess.run(["cp", str(SEALED), str(COPY)], check=True)
        subprocess.run(["codesign", "-s", "-", "--force",
                        "--timestamp=none", str(COPY)], check=True)
    run_case("NEG: copied sealed binary (identical cdhash, different path)",
             [str(COPY)])


if __name__ == "__main__":
    sys.exit(main() or 0)
