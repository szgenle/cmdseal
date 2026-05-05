#!/usr/bin/env python3
"""
cmdseal — Plan D: AEAD-sealed command wrapper.

GUI users: run `make app` instead; this CLI is for scripting,
CI pipelines, and audits.

Generates a capability-gated macOS binary from a shell-style command.
The full command is AES-256-GCM encrypted with a key K that lives in
the macOS Keychain, behind an ACL that only admits the generated
binary itself. At runtime the binary fetches K, decrypts the command
in-memory, and execvp()s it.

Subcommands:

  cmdseal seal    --command ... --output ...
      Create a new sealed binary + new keychain item.

  cmdseal rotate  --command ... --output ...
      Re-seal an existing binary: generates a fresh K, re-encrypts,
      overwrites the binary at --output, and replaces the old
      keychain item (the old K is destroyed).

Placeholders inside --command:

  {{secret:NAME}}   resolved at GENERATION time (you are prompted);
                    the resulting value is sealed into the ciphertext,
                    not stored separately. Nothing is asked at runtime.

  {{arg:N}}         resolved at RUNTIME from argv[N] of the generated
                    binary (1-based). Useful for things the caller
                    should control (e.g. a search term).

Example:

  cmdseal seal \\
      --command 'zhmm-cli -i ~/data.zmb --account you@example.com \\
                 --pwd {{secret:master}} -s {{arg:1}}' \\
      --output  ./fetch_pwd

The resulting ./fetch_pwd prompts for 'master' once at generation,
bakes it into the AEAD ciphertext, and thereafter runs silently as
  ./fetch_pwd <search_term>

macOS only. Requires: cc, codesign, /usr/bin/security.
"""

import argparse
import datetime
import getpass
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR      = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = SCRIPT_DIR / "runner_aead_template.c"
HELPER_SOURCE   = SCRIPT_DIR / "cmdseal_helper.c"
HELPER_BIN_DIR  = SCRIPT_DIR / "_build"
HELPER_BIN      = HELPER_BIN_DIR / "cmdseal_helper"

PLACEHOLDER_RE = re.compile(r"\{\{(secret|arg):([A-Za-z0-9_]+)\}\}")
SERVICE_RE     = re.compile(r"cmdseal\.[a-f0-9]{12}\.K")

# v1.2: inter-segment pipe separator token. Must match TOK_PIPE in
# runner_aead_template.c. See research/DESIGN.pipe.md §3.
TOK_PIPE_BYTE     = b"\x03"
MAX_PIPE_SEGMENTS = 8


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def mask_template(template):
    """Safely mask a command template for display.

    Rules (authoritative spec lives in tests/test_mask_template.py):
      1. First token (command name) is preserved verbatim.
      2. Tokens containing a ``{{arg:N}}`` / ``{{secret:NAME}}``
         placeholder are preserved verbatim.
      3. GNU long flags (``--``):
           * with ``=`` -> ``--key=***``
           * without ``=`` -> preserved
      4. POSIX short flags (``-``):
           * exactly two chars (``-p``) -> preserved
           * longer (``-pPass``, ``-xzvf``) -> first two chars + ``***``
      5. Any other bare token (including absolute paths) -> ``***``.

    Fallback: if shlex cannot parse the string (unclosed quote), we fall
    back to whitespace split but still mask every non-placeholder /
    non-flag token, so raw values never leak through.
    """
    if template is None:
        return ""
    s = template
    if not s.strip():
        return s
    try:
        tokens = shlex.split(s, posix=True)
    except ValueError:
        tokens = s.split()

    out = []
    for i, tok in enumerate(tokens):
        if i == 0:
            out.append(tok)
            continue
        if PLACEHOLDER_RE.search(tok):
            out.append(tok)
            continue
        if tok.startswith("--"):
            if "=" in tok:
                key, _ = tok.split("=", 1)
                out.append(f"{key}=***")
            else:
                out.append(tok)
            continue
        if tok.startswith("-") and len(tok) >= 2:
            if len(tok) == 2:
                out.append(tok)
            else:
                out.append(tok[:2] + "***")
            continue
        out.append("***")
    return " ".join(out)


def run(cmd, *, check=True, capture=False, input_bytes=None, input_text=None):
    """Small wrapper around subprocess for clearer errors."""
    try:
        kwargs = dict(check=check, capture_output=capture)
        if input_bytes is not None:
            kwargs["input"] = input_bytes
        elif input_text is not None:
            kwargs["input"] = input_text
            kwargs["text"] = True
        res = subprocess.run(cmd, **kwargs)
        return res
    except subprocess.CalledProcessError as e:
        print(f"cmdseal: command failed: {' '.join(cmd)}", file=sys.stderr)
        if e.stdout:
            out = e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", "replace")
            print(out, file=sys.stderr)
        if e.stderr:
            err = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", "replace")
            print(err, file=sys.stderr)
        sys.exit(e.returncode or 1)


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
        "--options", "runtime",    # hardened runtime: dyld drops DYLD_* env
        str(HELPER_BIN),
    ])


def check_platform_and_tools():
    if sys.platform != "darwin":
        sys.exit("cmdseal: macOS-only for v1.")
    for tool in ("cc", "codesign", "/usr/bin/security"):
        if "/" in tool:
            if not Path(tool).exists():
                sys.exit(f"cmdseal: missing required tool: {tool}")
        elif shutil.which(tool) is None:
            sys.exit(f"cmdseal: missing required tool: {tool}")


# ----------------------------------------------------------------------
# Command template tokenisation
# ----------------------------------------------------------------------

def classify_token(tok: str):
    """Return (kind, payload) where kind is 'literal'|'secret'|'arg'.

    A token is a 'placeholder' only if it is ENTIRELY a single
    placeholder. Mixed tokens are rejected.
    """
    m = PLACEHOLDER_RE.fullmatch(tok)
    if not m:
        if "{{" in tok and "}}" in tok:
            sys.exit(
                f"cmdseal: token {tok!r} mixes literal text with a "
                f"placeholder. Put the placeholder in its own argv "
                f"position instead."
            )
        return ("literal", tok)
    return (m.group(1), m.group(2))


def tokenize_command(command_str):
    try:
        raw = shlex.split(command_str)
    except ValueError as e:
        sys.exit(f"cmdseal: failed to parse --command: {e}")
    if not raw:
        sys.exit("cmdseal: --command must contain at least a program name")
    return [classify_token(t) for t in raw]


def resolve_program_path(tokens):
    """v1.1 #2: force the first token (program to exec) to be an
    absolute path. The sealed runner refuses PATH lookup, so we must
    bake a `/usr/bin/zip`-style path into the AEAD blob.

    If the user wrote e.g. `zip -j -P ...`, we call shutil.which('zip')
    at seal time and substitute the resolved absolute path. If the
    first token is itself a placeholder, bail out — that would mean
    the program name is user-controlled at runtime, which defeats the
    whole point of sealing a specific command.
    """
    if not tokens:
        return tokens
    first_kind, first_payload = tokens[0]
    if first_kind != "literal":
        sys.exit(
            "cmdseal: the first token (program name) cannot be a "
            f"{first_kind} placeholder. Write the program path "
            "literally, e.g. '/usr/bin/zip'."
        )
    if first_payload.startswith("/"):
        return tokens
    resolved = shutil.which(first_payload)
    if resolved is None:
        sys.exit(
            f"cmdseal: program {first_payload!r} not found in $PATH. "
            "Either install it or write an absolute path in --command."
        )
    print(f"[info] resolved {first_payload!r} -> {resolved!r}")
    return [("literal", resolved)] + list(tokens[1:])


# ----------------------------------------------------------------------
# Plaintext serialisation: NUL-terminated C strings, empty string = end
# ----------------------------------------------------------------------

def serialize_segments(segments, secret_values):
    """Build the plaintext blob the runner will walk at exec time.

    `segments` is a list of 1..N token lists (one per pipeline stage,
    upstream first). When N == 1 the output is BYTE-IDENTICAL to the
    v1.1 layout (no \x03 separator token anywhere), so existing
    callers see zero format regression.

    For N >= 2, a single-byte \x03 token is inserted between segments.
    See research/DESIGN.pipe.md §3.
    """
    parts = []
    for si, tokens in enumerate(segments):
        if si > 0:
            # Inter-segment separator. Rendered as the one-byte token
            # "\x03" — distinct from any shlex-produced literal and
            # from the \x02arg prefix.
            parts.append(TOK_PIPE_BYTE)
        for kind, payload in tokens:
            if kind == "literal":
                parts.append(payload.encode("utf-8"))
            elif kind == "secret":
                # Secrets are substituted in as literals at generation
                # time. Plan D keeps exactly ONE keychain item (for
                # K), not one per secret.
                parts.append(secret_values[payload].encode("utf-8"))
            elif kind == "arg":
                # "\x02arg:N" — runtime token resolved by the runner.
                parts.append(b"\x02arg:" + payload.encode("utf-8"))
            else:
                raise AssertionError(kind)
    # Tokens are NUL-separated; an extra empty NUL marks end of list.
    blob = b"\x00".join(parts) + b"\x00" + b"\x00"
    # Sanity: tokens must not contain raw NULs themselves.
    for p in parts:
        if b"\x00" in p:
            sys.exit("cmdseal: token contains a NUL byte (not supported)")
    return blob


# ----------------------------------------------------------------------
# AEAD via cmdseal_helper
# ----------------------------------------------------------------------

def aead_encrypt(plaintext_bytes, key_hex):
    """Returns (nonce:bytes[12], ciphertext:bytes, tag:bytes[16])."""
    ensure_helper_built()
    res = subprocess.run(
        [str(HELPER_BIN), "encrypt", key_hex],
        input=plaintext_bytes,
        capture_output=True,
    )
    if res.returncode != 0:
        sys.stderr.write(res.stderr.decode("utf-8", "replace"))
        sys.exit(f"cmdseal: helper encrypt failed (rc={res.returncode})")
    blob = res.stdout
    if len(blob) < 12 + 16:
        sys.exit("cmdseal: helper encrypt produced unexpectedly short output")
    nonce = blob[:12]
    tag   = blob[-16:]
    ct    = blob[12:-16]
    if len(ct) != len(plaintext_bytes):
        sys.exit("cmdseal: helper encrypt length mismatch (internal bug)")
    return nonce, ct, tag


def kc_add_key(service, account, key_hex, binary_path, comment_json=None):
    ensure_helper_built()
    argv = [str(HELPER_BIN), "add", service, account, binary_path]
    if comment_json:
        argv.append(comment_json)
    res = subprocess.run(
        argv,
        input=key_hex,
        text=True,
        capture_output=True,
    )
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        sys.exit(
            f"cmdseal: cmdseal_helper add failed (rc={res.returncode}) "
            f"for service={service}"
        )


def kc_list(service_prefix="cmdseal."):
    """Return a list of dicts describing every keychain item whose
    service starts with `service_prefix`. Zero ACL prompts (see
    NEXT.md §5.19 empirical validation).

    Each dict may contain: service, account, label, comment
    (raw string), created, modified (epoch seconds, float). Missing
    fields are simply absent.
    """
    ensure_helper_built()
    res = subprocess.run(
        [str(HELPER_BIN), "list", service_prefix],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        sys.exit(
            f"cmdseal: cmdseal_helper list failed (rc={res.returncode})"
        )
    try:
        return json.loads(res.stdout or "[]")
    except json.JSONDecodeError as e:
        sys.exit(f"cmdseal: helper list produced invalid JSON: {e}")


def kc_delete(service, account):
    """Best-effort delete; exit code 69 (not-found) is ignored."""
    ensure_helper_built()
    res = subprocess.run(
        [str(HELPER_BIN), "delete", service, account],
        capture_output=True, text=True,
    )
    if res.returncode not in (0, 69):
        sys.stderr.write(res.stderr)
        sys.exit(
            f"cmdseal: cmdseal_helper delete failed (rc={res.returncode}) "
            f"for service={service}"
        )


# ----------------------------------------------------------------------
# C source rendering
# ----------------------------------------------------------------------

def c_escape_string(s: str) -> str:
    """Escape a Python string for inclusion inside a C \"...\" literal.

    非 ASCII 字符按 UTF-8 字节展开（每个字节 \\xNN），而不是按 Unicode
    码点展开——C 的 \\x 转义会贪婪吞掉后续所有 hex 字符，若把 U+6D4B
    写成 \\x6d4b 会被当成一个超出 unsigned char 范围的字符，编译报
    \"hex escape sequence out of range\"。按 UTF-8 字节则每个 \\xNN
    正好两位，运行时输出流按 UTF-8 解析即可直通中文/emoji 等。

    为避免 C 将相邻 hex digit 合并到 \\x 里（例如 \"\\xe6\" + \"a\" 会变成
    \\xe6a），在 \\xNN 之后紧跟的 ASCII hex 字符（0-9a-fA-F）前会强制
    关闭字符串并重开：\"\\xe6\"\"a\"。
    """
    out = []
    prev_was_hex_escape = False
    for b in s.encode("utf-8"):
        if b == 0x5C:           # backslash
            out.append("\\\\")
            prev_was_hex_escape = False
        elif b == 0x22:         # double quote
            out.append('\\"')
            prev_was_hex_escape = False
        elif b == 0x0A:
            out.append("\\n")
            prev_was_hex_escape = False
        elif b == 0x0D:
            out.append("\\r")
            prev_was_hex_escape = False
        elif b == 0x09:
            out.append("\\t")
            prev_was_hex_escape = False
        elif 0x20 <= b < 0x7F:
            ch = chr(b)
            is_hex = ch in "0123456789abcdefABCDEF"
            if prev_was_hex_escape and is_hex:
                out.append('""')   # close + reopen to terminate \xNN
            out.append(ch)
            prev_was_hex_escape = False
        else:
            out.append(f"\\x{b:02x}")
            prev_was_hex_escape = True
    return "".join(out)


def c_byte_array(b: bytes) -> str:
    """Render `bytes` as a comma-separated list of C hex bytes."""
    if not b:
        return "0"
    lines = []
    for i in range(0, len(b), 16):
        chunk = b[i:i + 16]
        lines.append("    " + ", ".join(f"0x{x:02x}" for x in chunk) + ",")
    body = "\n".join(lines)
    # Drop the trailing comma on the last byte (cosmetic; C tolerates it,
    # but cleaner without).
    if body.endswith(","):
        body = body[:-1]
    return body


def render_source(template_src, *, kc_service, kc_account, label,
                  nonce, ciphertext, tag):
    def repl_string_marker(src, marker, value):
        pat = re.compile(
            r'/\*\s*@@' + re.escape(marker) + r'@@\s*\*/\s*"[^"]*"',
            re.DOTALL)
        repl = f'/* @@{marker}@@ */ "{c_escape_string(value)}"'
        new, n = pat.subn(lambda _m: repl, src, count=1)
        if n != 1:
            sys.exit(f"cmdseal: string marker {marker} not found in template")
        return new

    def repl_array_marker(src, marker, body):
        pat = re.compile(
            r'/\*\s*@@' + re.escape(marker) + r'@@\s*\*/\s*\{[^}]*\}',
            re.DOTALL)
        repl = "/* @@" + marker + "@@ */ {\n" + body + "\n}"
        new, n = pat.subn(lambda _m: repl, src, count=1)
        if n != 1:
            sys.exit(f"cmdseal: array marker {marker} not found in template")
        return new

    def repl_int_marker(src, marker, value):
        pat = re.compile(
            r'/\*\s*@@' + re.escape(marker) + r'@@\s*\*/\s*\d+',
            re.DOTALL)
        repl = f"/* @@{marker}@@ */ {value}"
        new, n = pat.subn(lambda _m: repl, src, count=1)
        if n != 1:
            sys.exit(f"cmdseal: int marker {marker} not found in template")
        return new

    src = template_src
    src = repl_string_marker(src, "KC_SERVICE", kc_service)
    src = repl_string_marker(src, "KC_ACCOUNT", kc_account)
    src = repl_string_marker(src, "LABEL", label)
    src = repl_array_marker(src, "NONCE",      c_byte_array(nonce))
    src = repl_array_marker(src, "CIPHERTEXT", c_byte_array(ciphertext))
    src = repl_int_marker(src, "CIPHERTEXT_LEN", len(ciphertext))
    src = repl_array_marker(src, "TAG",        c_byte_array(tag))
    return src


# ----------------------------------------------------------------------
# Secret collection (generation-time prompts)
# ----------------------------------------------------------------------

def collect_secrets(secret_names, secrets_from_stdin):
    if not secret_names:
        return {}
    if secrets_from_stdin:
        return read_secrets_from_stdin(secret_names)
    values = {}
    for name in secret_names:
        value = getpass.getpass(f"Enter secret value for '{name}': ")
        if not value:
            sys.exit(f"cmdseal: empty secret for '{name}', aborting.")
        confirm = getpass.getpass(f"Confirm '{name}': ")
        if value != confirm:
            sys.exit("cmdseal: values did not match, aborting.")
        values[name] = value
    return values


def read_secrets_from_stdin(required_names):
    values = {}
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line:
            continue
        if "=" not in line:
            sys.exit(f"cmdseal: malformed secret line: {line!r} "
                     f"(expected NAME=VALUE)")
        name, _, value = line.partition("=")
        name = name.strip()
        if not name:
            sys.exit(f"cmdseal: empty secret name in line: {line!r}")
        values[name] = value
    missing = [n for n in required_names if n not in values]
    if missing:
        sys.exit(
            f"cmdseal: missing secrets on stdin: {', '.join(missing)}"
        )
    extra = [n for n in values if n not in required_names]
    if extra:
        print(f"cmdseal: warning: ignoring unused secrets: "
              f"{', '.join(extra)}", file=sys.stderr)
    return {n: values[n] for n in required_names}


# ----------------------------------------------------------------------
# Build + sign
# ----------------------------------------------------------------------

def build_and_sign(src_text, output_path, signing_identity, do_sign):
    build_dir = Path(tempfile.mkdtemp(prefix="cmdseal_"))
    src_path  = build_dir / "runner.c"
    src_path.write_text(src_text)

    print(f"[1/4] compiling -> {output_path}")
    run([
        "cc", "-O2", "-Wall", "-Wno-deprecated-declarations",
        "-o", str(output_path),
        str(src_path),
        "-framework", "Security",
        "-framework", "CoreFoundation",
    ])

    if do_sign:
        if signing_identity == "-":
            print("[2/4] ad-hoc signing "
                  "(WEAK: see DESIGN.md §8 for enforcement caveats)")
        else:
            print(f"[2/4] signing with identity: {signing_identity}")
        run([
            "codesign", "-s", signing_identity,
            "--force", "--timestamp=none",
            "--options", "runtime",    # hardened runtime (v1.1 #4)
            str(output_path),
        ])
    else:
        print("[2/4] skipped signing (--no-sign)")

    return build_dir, src_path


# ----------------------------------------------------------------------
# Binary metadata extraction (for rotate)
# ----------------------------------------------------------------------

def extract_service_from_binary(binary_path):
    """Return the 'cmdseal.HASH.K' service name embedded in an existing
    sealed binary, via `strings`. Returns None if not found."""
    res = subprocess.run(
        ["strings", str(binary_path)],
        capture_output=True, text=True,
    )
    for line in res.stdout.splitlines():
        m = SERVICE_RE.fullmatch(line.strip())
        if m:
            return m.group(0)
    return None


# ----------------------------------------------------------------------
# Seal / rotate
# ----------------------------------------------------------------------

def do_seal(args, *, old_service_to_delete=None):
    check_platform_and_tools()

    if not args.user:
        sys.exit("cmdseal: cannot determine keychain account "
                 "(set $USER or pass --user)")

    template_path = Path(args.template)
    if not template_path.is_file():
        sys.exit(f"cmdseal: template not found: {template_path}")

    # 1. Tokenise each segment + gather secrets.
    #    v1.2: --command is action="append", so args.command is a list
    #    of 1..N shell-like strings forming a stdout→stdin pipeline.
    commands = args.command
    if not commands:
        sys.exit("cmdseal: --command is required")
    if len(commands) > MAX_PIPE_SEGMENTS:
        sys.exit(
            f"cmdseal: too many --command segments "
            f"({len(commands)}); max is {MAX_PIPE_SEGMENTS}"
        )

    segments = []
    for cmd_str in commands:
        toks = tokenize_command(cmd_str)
        # v1.1 #2: resolve non-absolute program name at seal time
        # (applies per segment — every stage must have an absolute
        # path baked in, so the runner never does PATH lookup).
        toks = resolve_program_path(toks)
        segments.append(toks)

    # Secrets and positional args are collected ACROSS segments:
    # {{arg:N}} numbering is global (see DESIGN.pipe.md §2.2).
    secret_names = sorted({payload
                           for seg in segments
                           for kind, payload in seg
                           if kind == "secret"})
    secret_values = collect_secrets(secret_names, args.secrets_from_stdin)

    # 2. Build identity (new per seal — rotate generates fresh UUID too).
    short_hash  = secrets.token_hex(6)            # 12 hex chars
    kc_service  = f"cmdseal.{short_hash}.K"
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    label = args.label or f"cmdseal sealed: {output_path.name}"

    # 3. Serialise + encrypt.
    plaintext = serialize_segments(segments, secret_values)
    # Defensive: wipe secret_values from memory.
    secret_values.clear()

    key_bytes = secrets.token_bytes(32)
    key_hex   = key_bytes.hex()

    nonce, ciphertext, tag = aead_encrypt(plaintext, key_hex)

    # 4. Render + build + sign.
    template_src = template_path.read_text()
    rendered = render_source(
        template_src,
        kc_service=kc_service,
        kc_account=args.user,
        label=label,
        nonce=nonce,
        ciphertext=ciphertext,
        tag=tag,
    )

    build_dir, src_path = build_and_sign(
        rendered, output_path, args.signing_identity, not args.no_sign)

    # 5. If rotating: destroy the OLD keychain item first (AFTER we
    #    have a good new binary in place, so a failure mid-seal leaves
    #    the old binary+item pair intact for recovery).
    if old_service_to_delete and old_service_to_delete != kc_service:
        print(f"[3/4] deleting old keychain item: {old_service_to_delete}")
        kc_delete(old_service_to_delete, args.user)
        kc_step_label = "[3/4] writing new keychain item"
    else:
        kc_step_label = "[3/4] writing keychain item"

    # 6. Store K in keychain, bound to the new binary's cdhash.
    #    Along with K we write a small JSON blob into kSecAttrComment
    #    describing this runner (label, original template, output path,
    #    arg arity, secret names, creation timestamp). This blob is
    #    readable by any same-user process without firing the ACL
    #    dialog (NEXT.md §5.19) — the GUI uses it to enumerate
    #    sealed runners with zero popups. It does NOT contain K, the
    #    secret values, or any AEAD material.
    positional_args = sorted({int(payload)
                              for seg in segments
                              for kind, payload in seg
                              if kind == "arg"})
    arity = max(positional_args) if positional_args else 0
    # Human-readable template string ("cmd1 | cmd2 | cmd3"), stored
    # with ALL positional / bare values masked via mask_template() so
    # that the keychain comment NEVER contains plaintext values. The
    # real tokens only live inside the AEAD ciphertext baked into the
    # sealed binary (which requires the matching cdhash + K to open).
    # Consequence: `cmdseal list` / GUI / any downstream consumer of
    # the comment JSON will see `***` for bare positional args, and
    # full text for command name / `-flag` / `{{placeholder}}` tokens.
    # For multi-segment runners we ALSO emit a structured `segments`
    # list (each segment masked independently, so GUI can round-trip
    # the pipeline without the ``|`` being swallowed by shlex).
    masked_segments = [mask_template(c) for c in commands]
    template_display = " | ".join(masked_segments)
    comment_payload = {
        "v": 1,
        "label": label,
        "template": template_display,
        "output_path": str(output_path),
        "arity": arity,
        "secret_names": secret_names,
        "created_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    if len(commands) > 1:
        comment_payload["segments"] = masked_segments
    comment_json = json.dumps(comment_payload,
                              ensure_ascii=False, separators=(",", ":"))

    print(kc_step_label)
    kc_add_key(
        service=kc_service,
        account=args.user,
        key_hex=key_hex,
        binary_path=str(output_path),
        comment_json=comment_json,
    )

    # 7. Cleanup.
    if args.keep_source:
        print(f"[4/4] source kept: {src_path}")
    else:
        shutil.rmtree(build_dir, ignore_errors=True)
        print("[4/4] cleaned up build dir")

    # 8. Summary.
    usage_hint = str(output_path)
    for n in positional_args:
        usage_hint += f" <arg{n}>"

    print()
    print("✓ sealed." + (" (rotated)" if old_service_to_delete else ""))
    print(f"  binary      : {output_path}")
    print(f"  kc service  : {kc_service}")
    print(f"  kc account  : {args.user}")
    print(f"  sealed secrets : "
          f"{', '.join(secret_names) if secret_names else '(none)'}")
    print(f"  usage       : {usage_hint}")
    print()
    if secret_names:
        print("Note: secret values were sealed into the AEAD ciphertext "
              "at generation; you will not be prompted again at runtime.")
    return 0


def do_rotate(args):
    output_path = Path(args.output).expanduser().resolve()
    if not output_path.exists():
        sys.exit(f"cmdseal rotate: no existing binary at {output_path} "
                 f"(use `cmdseal seal` instead for new binaries)")
    old_service = extract_service_from_binary(output_path)
    if old_service is None:
        print(f"cmdseal rotate: warning — cannot locate old service name "
              f"in {output_path}; proceeding without cleaning up the old "
              f"keychain item (orphan may remain).", file=sys.stderr)
    else:
        print(f"[*] old keychain service : {old_service}")
    return do_seal(args, old_service_to_delete=old_service)


def do_list(args):
    """Enumerate sealed runners. Zero ACL prompts.

    Default: human-readable table.
    --json: emit raw JSON array (one object per item) for GUI / scripting.
    """
    check_platform_and_tools()
    items = kc_list(args.prefix)

    # Parse each item's comment into a nested dict when possible.
    for it in items:
        raw = it.get("comment")
        if raw:
            try:
                it["_meta"] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                it["_meta"] = None
        else:
            it["_meta"] = None

    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0

    if not items:
        print(f"(no sealed runners found with prefix {args.prefix!r})")
        return 0

    print(f"{len(items)} sealed runner(s):\n")
    for it in items:
        svc = it.get("service", "?")
        meta = it.get("_meta")
        if meta:
            label = meta.get("label", "")
            out   = meta.get("output_path", "")
            tmpl  = meta.get("template", "")
            arity = meta.get("arity", 0)
            secs  = meta.get("secret_names") or []
            created = meta.get("created_at", "")
            print(f"  • {label}")
            print(f"      service : {svc}")
            print(f"      output  : {out}")
            print(f"      template: {tmpl}")
            print(f"      arity   : {arity} positional arg(s)")
            print(f"      secrets : {', '.join(secs) if secs else '(none)'}")
            print(f"      created : {created}")
        else:
            # Legacy item: sealed before kSecAttrComment was written.
            print(f"  • (legacy, metadata unknown)")
            print(f"      service : {svc}")
            print(f"      account : {it.get('account', '?')}")
        print()
    return 0


def do_delete(args):
    """Delete a single runner's keychain key by service+account.

    The on-disk binary is NOT touched — it will become unusable (AEAD
    cannot unwrap without its K). Caller must decide whether to remove
    the stale binary separately.
    """
    check_platform_and_tools()
    kc_delete(args.service, args.user)
    print(f"cmdseal: deleted keychain item "
          f"(service={args.service}, account={args.user})")
    return 0


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def add_common_seal_args(p):
    # v1.2: action="append" — pass --command multiple times to form a
    # stdout→stdin pipeline. A single --command keeps v1.1 semantics
    # and produces a byte-identical plaintext layout.
    p.add_argument("--command", required=True, action="append",
                   metavar="CMD",
                   help="command template (shell-quoted string). "
                        "Pass multiple times to form a pipeline: "
                        "cmd1 | cmd2 | ... (max "
                        f"{MAX_PIPE_SEGMENTS} segments).")
    p.add_argument("--output", required=True,
                   help="path to write the generated binary")
    p.add_argument("--template", default=str(DEFAULT_TEMPLATE),
                   help=f"path to runner template "
                        f"(default: {DEFAULT_TEMPLATE})")
    p.add_argument("--user", default=os.environ.get("USER", ""),
                   help="keychain account name (default: $USER)")
    p.add_argument("--label", default="",
                   help="human-readable label "
                        "(default: derived from output)")
    p.add_argument("--no-sign", action="store_true",
                   help="skip codesign step (dev only)")
    p.add_argument("--signing-identity", default="-",
                   help="identity passed to `codesign -s`. Default '-' "
                        "means ad-hoc (WEAK; see DESIGN.md §8). Pass "
                        "e.g. 'Developer ID Application: You (TEAMID)'.")
    p.add_argument("--keep-source", action="store_true",
                   help="keep the intermediate .c file for inspection")
    p.add_argument("--secrets-from-stdin", action="store_true",
                   help="read secrets as NAME=VALUE lines from stdin "
                        "(for scripting / GUI front-ends)")


def parse_args():
    p = argparse.ArgumentParser(
        prog="cmdseal",
        description=(
            "Seal a command line into an AEAD-encrypted, keychain-gated "
            "macOS binary (Plan D). See NEXT.md §5 for the design."
        ),
    )
    sub = p.add_subparsers(dest="subcommand")

    ps = sub.add_parser("seal", help="create a new sealed binary")
    add_common_seal_args(ps)

    pr = sub.add_parser("rotate",
                        help="rotate: re-seal with a fresh K + new "
                             "keychain item (overwrites --output)")
    add_common_seal_args(pr)

    pl = sub.add_parser("list",
                        help="list sealed runners (read-only, zero popups)")
    pl.add_argument("--prefix", default="cmdseal.",
                    help="service prefix to match (default: cmdseal.)")
    pl.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON instead of a table")

    pd = sub.add_parser("delete",
                        help="delete a sealed runner's keychain key "
                             "(the on-disk binary is NOT touched; it will "
                             "become unusable without its K)")
    pd.add_argument("--service", required=True,
                    help="keychain service name, e.g. cmdseal.ab12cd34.K")
    pd.add_argument("--user", default=os.environ.get("USER", "root"),
                    help="account name (default: $USER)")

    # Back-compat: if the user passes --command/--output at the top
    # level with no subcommand, treat as `seal`.
    if len(sys.argv) >= 2 and sys.argv[1] not in (
            "seal", "rotate", "list", "delete",
            "-h", "--help"):
        # Inject default subcommand.
        args = p.parse_args(["seal"] + sys.argv[1:])
    else:
        args = p.parse_args()
        if args.subcommand is None:
            p.print_help()
            sys.exit(0)
    return args


def main():
    args = parse_args()
    if args.subcommand == "seal":
        return do_seal(args)
    elif args.subcommand == "rotate":
        return do_rotate(args)
    elif args.subcommand == "list":
        return do_list(args)
    elif args.subcommand == "delete":
        return do_delete(args)
    else:
        sys.exit(f"cmdseal: unknown subcommand {args.subcommand!r}")


if __name__ == "__main__":
    sys.exit(main() or 0)
