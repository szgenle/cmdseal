#!/usr/bin/env python3
"""
cmdseal — generate a capability-gated macOS binary from a command template.

A command template is a shell-like string with two kinds of placeholders:

    {{secret:NAME}}   resolved at runtime from macOS Keychain
                      (you are prompted to enter the value NOW)
    {{arg:N}}         resolved at runtime from argv[N] of the generated
                      binary (1-based)

Example:

    cmdseal --output ./fetch_pwd \\
      --command 'zhmm_cmd -i /Users/ws/data.gl \\
                 --pwd {{secret:master}} --search {{arg:1}}'

The resulting ./fetch_pwd:
  - reads "master" from macOS Keychain (ACL-bound to this exact binary),
  - takes a search term from its own argv[1],
  - execvp()s the final command.

macOS only. Requires: cc, codesign, /usr/bin/security.
"""

import argparse
import getpass
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = SCRIPT_DIR / "wrapper_template.c"
HELPER_SOURCE   = SCRIPT_DIR / "cmdseal_helper.c"
HELPER_BIN_DIR  = SCRIPT_DIR / "_build"
HELPER_BIN      = HELPER_BIN_DIR / "cmdseal_helper"

PLACEHOLDER_RE = re.compile(r"\{\{(secret|arg):([A-Za-z0-9_]+)\}\}")


def c_escape(s: str) -> str:
    """Escape a Python string for inclusion inside a C "..." literal."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif 0x20 <= o < 0x7F:
            out.append(ch)
        else:
            out.append(f"\\x{o:02x}")
    return "".join(out)


def classify_token(tok: str):
    """Return (kind, payload) where kind is 'literal'|'secret'|'arg'.

    A token is a "placeholder" only if it is ENTIRELY a single placeholder.
    Mixed tokens (e.g. "prefix-{{secret:x}}") are rejected — users should
    just split them if they need that.
    """
    m = PLACEHOLDER_RE.fullmatch(tok)
    if not m:
        if "{{" in tok and "}}" in tok:
            raise SystemExit(
                f"cmdseal: token {tok!r} mixes literal text with a "
                f"placeholder. Put the placeholder in its own argv "
                f"position instead."
            )
        return ("literal", tok)
    return (m.group(1), m.group(2))


def render_c(template_src: str, *, service_prefix: str, kc_account: str,
             tokens: list, label: str) -> str:
    """Fill the /* @@...@@ */ markers in the template source."""

    def repl_string(src: str, marker: str, value: str) -> str:
        pattern = re.compile(
            r'/\*\s*@@' + re.escape(marker) + r'@@\s*\*/\s*"[^"]*"',
            re.DOTALL,
        )
        replacement = f'/* @@{marker}@@ */ "{c_escape(value)}"'
        new, n = pattern.subn(lambda _m: replacement, src, count=1)
        if n != 1:
            raise SystemExit(f"cmdseal: marker {marker} not found in template")
        return new

    def repl_block(src: str, marker: str, block: str) -> str:
        # Replace "/* @@TOKENS@@ */ { ... }" (the entire brace-enclosed list).
        pattern = re.compile(
            r'/\*\s*@@' + re.escape(marker) + r'@@\s*\*/\s*\{[^}]*\}',
            re.DOTALL,
        )
        replacement = f'/* @@{marker}@@ */ {block}'
        new, n = pattern.subn(lambda _m: replacement, src, count=1)
        if n != 1:
            raise SystemExit(f"cmdseal: block marker {marker} not found")
        return new

    tokens_c_lines = []
    for kind, payload in tokens:
        if kind == "literal":
            tokens_c_lines.append(f'    "{c_escape(payload)}",')
        elif kind == "secret":
            # Use adjacent-string concat to stop the \xNN hex escape from
            # greedily consuming following hex digits.
            tokens_c_lines.append(
                f'    "\\x01" "secret:{c_escape(payload)}",'
            )
        elif kind == "arg":
            tokens_c_lines.append(
                f'    "\\x02" "arg:{c_escape(payload)}",'
            )
        else:
            raise AssertionError(kind)
    tokens_c_lines.append("    NULL")
    tokens_block = "{\n" + "\n".join(tokens_c_lines) + "\n}"

    src = template_src
    src = repl_string(src, "SERVICE_PREFIX", service_prefix)
    src = repl_string(src, "KC_ACCOUNT", kc_account)
    src = repl_string(src, "LABEL", label)
    src = repl_block(src, "TOKENS", tokens_block)
    return src


def run(cmd, *, check=True, capture=False, input_text=None):
    """Small wrapper around subprocess for clearer errors."""
    try:
        res = subprocess.run(
            cmd,
            check=check,
            text=True,
            input=input_text,
            capture_output=capture,
        )
        return res
    except subprocess.CalledProcessError as e:
        print(f"cmdseal: command failed: {' '.join(cmd)}", file=sys.stderr)
        if e.stdout:
            print(e.stdout, file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(e.returncode or 1)


def add_keychain_entry(*, service: str, account: str, secret: str,
                       binary_path: str, update: bool):
    """Add or replace a generic-password entry with a strict single-app
    ACL via cmdseal_helper (which uses SecAccessCreate directly, avoiding
    /usr/bin/security being auto-added to the trusted list)."""
    _ = update  # always replace; helper handles idempotency
    ensure_helper_built()
    res = subprocess.run(
        [str(HELPER_BIN), "add", service, account, binary_path],
        input=secret,
        text=True,
        capture_output=True,
    )
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        sys.exit(
            f"cmdseal: cmdseal_helper failed (rc={res.returncode}) "
            f"for service={service}"
        )


def ensure_helper_built():
    """Compile + ad-hoc sign cmdseal_helper if missing or outdated."""
    if (HELPER_BIN.exists()
            and HELPER_BIN.stat().st_mtime >= HELPER_SOURCE.stat().st_mtime):
        return
    HELPER_BIN_DIR.mkdir(parents=True, exist_ok=True)
    print("[*] building cmdseal_helper ...")
    run([
        "cc", "-O2", "-Wall", "-Wno-deprecated-declarations",
        "-o", str(HELPER_BIN),
        str(HELPER_SOURCE),
        "-framework", "Security",
        "-framework", "CoreFoundation",
    ])
    run([
        "codesign", "-s", "-", "--force", "--timestamp=none",
        str(HELPER_BIN),
    ])


def parse_args():
    p = argparse.ArgumentParser(
        prog="cmdseal",
        description="Seal a command line into a keychain-bound macOS binary.",
    )
    p.add_argument("--command", required=True,
                   help="command template (shell-quoted string)")
    p.add_argument("--output", required=True,
                   help="path to write the generated binary")
    p.add_argument("--template", default=str(DEFAULT_TEMPLATE),
                   help=f"path to wrapper_template.c "
                        f"(default: {DEFAULT_TEMPLATE})")
    p.add_argument("--user", default=os.environ.get("USER", ""),
                   help="keychain account name (default: $USER)")
    p.add_argument("--label", default="",
                   help="human-readable label (default: derived from output)")
    p.add_argument("--service-prefix", default="",
                   help="override service prefix (default: cmdseal.<hash>)")
    p.add_argument("--no-sign", action="store_true",
                   help="skip codesign step (dev only)")
    p.add_argument("--signing-identity",
                   default="-",
                   help="code-signing identity passed to `codesign -s`. "
                        "Default '-' means ad-hoc (WEAK enforcement: see "
                        "DESIGN.md §8). Pass e.g. "
                        "'Developer ID Application: You (TEAMID)' for "
                        "real keychain ACL enforcement.")
    p.add_argument("--keep-source", action="store_true",
                   help="keep the intermediate .c file for inspection")
    p.add_argument("--secrets-from-stdin", action="store_true",
                   help="read secrets as NAME=VALUE lines from stdin "
                        "(one per line) instead of prompting. "
                        "Intended for scripting and the GUI front-end.")
    return p.parse_args()


def read_secrets_from_stdin(required_names):
    """Read NAME=VALUE lines from stdin until EOF.

    Returns a dict. Raises SystemExit on malformed input or missing names.
    """
    values = {}
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line:
            continue
        if "=" not in line:
            raise SystemExit(f"cmdseal: malformed secret line: {line!r} "
                             f"(expected NAME=VALUE)")
        name, _, value = line.partition("=")
        name = name.strip()
        if not name:
            raise SystemExit(f"cmdseal: empty secret name in line: {line!r}")
        values[name] = value
    missing = [n for n in required_names if n not in values]
    if missing:
        raise SystemExit(
            f"cmdseal: missing secrets on stdin: {', '.join(missing)}"
        )
    extra = [n for n in values if n not in required_names]
    if extra:
        print(f"cmdseal: warning: ignoring unused secrets: "
              f"{', '.join(extra)}", file=sys.stderr)
    return {n: values[n] for n in required_names}


def main() -> int:
    if sys.platform != "darwin":
        print("cmdseal: macOS-only for v1.", file=sys.stderr)
        return 1

    args = parse_args()

    if not args.user:
        print("cmdseal: cannot determine keychain account "
              "(set $USER or pass --user)", file=sys.stderr)
        return 1

    template_path = Path(args.template)
    if not template_path.is_file():
        print(f"cmdseal: template not found: {template_path}", file=sys.stderr)
        return 1

    for tool in ("cc", "codesign", "/usr/bin/security"):
        if "/" in tool:
            if not Path(tool).exists():
                print(f"cmdseal: missing required tool: {tool}",
                      file=sys.stderr)
                return 1
        elif shutil.which(tool) is None:
            print(f"cmdseal: missing required tool: {tool}", file=sys.stderr)
            return 1

    # 1. Tokenize the command template.
    try:
        raw_tokens = shlex.split(args.command)
    except ValueError as e:
        print(f"cmdseal: failed to parse --command: {e}", file=sys.stderr)
        return 1
    if not raw_tokens:
        print("cmdseal: --command must contain at least a program name",
              file=sys.stderr)
        return 1

    tokens = [classify_token(t) for t in raw_tokens]
    secret_names = sorted({payload for kind, payload in tokens
                           if kind == "secret"})

    # 2. Collect secret values (stdin-scripted or interactive).
    if args.secrets_from_stdin:
        secret_values = read_secrets_from_stdin(secret_names)
    else:
        secret_values = {}
        for name in secret_names:
            value = getpass.getpass(f"Enter secret value for '{name}': ")
            if not value:
                print(f"cmdseal: empty secret for '{name}', aborting.",
                      file=sys.stderr)
                return 1
            confirm = getpass.getpass(f"Confirm '{name}': ")
            if value != confirm:
                print("cmdseal: values did not match, aborting.",
                      file=sys.stderr)
                return 1
            secret_values[name] = value

    # 3. Build identity.
    short_hash = uuid.uuid4().hex[:12]
    service_prefix = (args.service_prefix or f"cmdseal.{short_hash}")
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    label = args.label or f"cmdseal sealed: {output_path.name}"

    # 4. Render C source.
    template_src = template_path.read_text()
    rendered = render_c(
        template_src,
        service_prefix=service_prefix,
        kc_account=args.user,
        tokens=tokens,
        label=label,
    )

    build_dir = Path(tempfile.mkdtemp(prefix="cmdseal_"))
    src_path = build_dir / "wrapper.c"
    src_path.write_text(rendered)

    # 5. Compile.
    print(f"[1/4] compiling -> {output_path}")
    run([
        "cc", "-O2", "-Wall", "-Wno-deprecated-declarations",
        "-o", str(output_path),
        str(src_path),
        "-framework", "Security",
        "-framework", "CoreFoundation",
    ])

    # 6. Sign.
    if not args.no_sign:
        if args.signing_identity == "-":
            print("[2/4] ad-hoc signing "
                  "(WEAK: see DESIGN.md §8 for enforcement caveats)")
        else:
            print(f"[2/4] signing with identity: {args.signing_identity}")
        run([
            "codesign", "-s", args.signing_identity,
            "--force", "--timestamp=none",
            str(output_path),
        ])
    else:
        print("[2/4] skipped signing (--no-sign)")

    # 7. Write keychain entries with ACL bound to this binary.
    print(f"[3/4] writing {len(secret_names)} keychain entr"
          f"{'y' if len(secret_names) == 1 else 'ies'}")
    for name in secret_names:
        svc = f"{service_prefix}.{name}"
        add_keychain_entry(
            service=svc,
            account=args.user,
            secret=secret_values[name],
            binary_path=str(output_path),
            update=True,
        )

    # 8. Optional cleanup.
    if args.keep_source:
        print(f"[4/4] source kept: {src_path}")
    else:
        shutil.rmtree(build_dir, ignore_errors=True)
        print("[4/4] cleaned up build dir")

    # 9. Summary.
    positional_args = sorted({int(payload) for kind, payload in tokens
                              if kind == "arg"})
    usage_hint = str(output_path)
    for n in positional_args:
        usage_hint += f" <arg{n}>"

    print()
    print("✓ sealed.")
    print(f"  binary         : {output_path}")
    print(f"  service prefix : {service_prefix}")
    print(f"  account        : {args.user}")
    print(f"  secrets        : "
          f"{', '.join(secret_names) if secret_names else '(none)'}")
    print(f"  usage          : {usage_hint}")
    print()
    print("First invocation may trigger a one-time keychain prompt. "
          "Click 'Always Allow' for subsequent silent access.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
