# Changelog

> 中文版：[CHANGELOG.zh.md](./CHANGELOG.zh.md)

All notable changes to `cmdseal` are documented here.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
on the `cmdseal` (CLI + runner) surface. The `cmdseal-gui` PySide6
front-end package in [`pyproject.toml`](./pyproject.toml) carries its
own independent version number and is not required to stay in lock-step.

## [1.2.1] - Unreleased

GUI companion release for v1.2. Brings the multi-segment pipe
capability from the CLI to **both** PySide6 wizards so users can
compose pipelines visually.

### Added

- **Multi-segment editor in the seal wizard (advanced mode).** The
  *Command* page now hosts a stack of up to 8 pipe-segment editors
  with a `[+ Add pipe segment]` button and per-segment `[×]` remove.
  Each segment shows its own token count / secret / arg inspection,
  while a footer summarises the cross-segment totals (segments,
  global `{{arg:N}}` set, merged secret names).
- **Multi-segment chip editor in the template wizard (novice mode).**
  The *Command input* page accepts up to 8 pipe segments; the
  *Parameter selection* page renders one chip row per segment with
  `{{arg:N}}` numbering globally incrementing across segments. The
  whole pipeline is dry-run end-to-end via a chained `QProcess`
  graph (`setStandardOutputProcess`), exactly matching the
  runner's pipeline semantics at runtime.
- **Cross-segment secret merging.** `SecretsPage` now scans every
  segment and deduplicates secret names, preserving the CLI's
  global semantics.
- **Per-segment argv preview.** `ExecutePage` renders each pipe
  segment on its own `seg N :` line with secrets redacted to `***`.
- **`SealRequest.commands: list[str]`.** `gui/backend.py` now
  emits one `--command` per segment when building the `cmdseal.py`
  invocation, matching the CLI's `action="append"` behaviour.

### Fixed

- **Template wizard dangling reference.** After v1.2.1 renamed the
  `SealRequest.command` field to `commands: list[str]`,
  `template_wizard.ExecutionPage._build_request` was still passing
  `command=` as a keyword argument and would `TypeError` at the
  final step of the novice-mode wizard. Now it calls
  `commands=param_page.templates()` and round-trips through the
  multi-segment path.
- **`cmdseal.py edit-template` subcommand now actually exists.**
  Both the Runner Management window's right-click “Edit template…”
  action and [`gui/backend.py::edit_template`](./gui/backend.py)
  were invoking `python3 cmdseal.py edit-template …`, but the CLI
  only declared `seal / rotate / list / delete` subparsers. Worse,
  the back-compat shim in `parse_args` silently rewrote unknown
  first-tokens as `seal` arguments, producing a misleading
  “`seal`: the following arguments are required: --output” error
  instead of an “invalid choice”. Fix:
    - Added `do_edit_template(args)` that locates the old item by
      `--service`, reads the preserved fields (`output_path`, `label`,
      `account`, `secret_names`) from its `kSecAttrComment` metadata,
      enforces that the new template's `{{secret:NAME}}` set equals
      the old set, then delegates to `do_seal(old_service_to_delete=…)`
      for a single atomic “new K → recompile → re-sign → swap keychain
      item” flow.
    - Legacy items (no comment metadata) are rejected with a
      deterministic error message.
    - The shim whitelist was extended with `"edit-template"` so
      future typos surface as `argparse: invalid choice` rather
      than being absorbed into `seal`.

### Security

- No change to the security posture. GUI remains a thin wrapper
  over `cmdseal.py`; no encryption or dispatch logic is duplicated.
  The `--command` contract with the CLI is preserved verbatim,
  so all v1.2 runner-side guarantees (no shell, absolute path,
  `DYLD_*` stripping, hardened runtime) carry through unchanged.
- **Pipeline dry-run stays off the shell.** The template wizard's
  "Run entire pipeline" button uses a chained `QProcess` graph; the
  `|` character typed in a single segment is **not** treated as a
  pipe delimiter (a warning banner spells this out, and the user is
  directed to the `[+ Add pipe segment]` button instead).

### Compatibility

- A single-segment wizard session (either mode) produces the exact
  same CLI invocation as v1.1.
- `SealRequest.command` is kept as a read-only compatibility
  property (returns first segment) to avoid breaking downstream
  log / preview callers.
- `build_template(tokens, selected)` is retained as a thin wrapper
  over the new `build_template_many([tokens], [selected])`; the
  existing unit-test suite passes unchanged.

## [1.2.0] - Unreleased

Pipe-support release. Adds multi-segment pipelines to sealed binaries
while preserving the v1.1 security model (no shell at runtime, absolute
paths, `DYLD_*` stripped, hardened runtime). Design: [research/DESIGN.pipe.md](./research/DESIGN.pipe.md).

### Added

- **Multi-segment `--command`.** `cmdseal seal` now accepts the flag
  multiple times to build a `cmd_A | cmd_B | ... | cmd_N` pipeline
  (up to 8 segments). `{{arg:N}}` placeholders are globally numbered
  across all segments so the caller still sees a single positional
  argument list.
- **In-runner pipeline execution.** The generated runner implements
  its own `pipe()`+`fork()`+`dup2()` dispatcher in C (see
  `run_pipeline()` in `runner_aead_template.c`). **No shell is ever
  invoked at runtime**; each segment still runs through `execv()` and
  inherits the v1.1 hardening (absolute-path check, `DYLD_*` /
  `LD_*` stripped before fork).
- **pipefail-equivalent exit semantics.** If any segment exits
  non-zero, the sealed binary exits with the **left-most** failing
  code; all segments still run to completion, mirroring
  `set -o pipefail` in shells. Safety tools should fail loudly.
- **Byte-level v1.1 compatibility.** A single `--command` produces
  a plaintext blob byte-identical to v1.1 and takes the no-`fork`
  fast path in the runner. Zero regression risk for existing users.
- **Tests.** New `tests/test_pipe_serialize.py` (pure-Python,
  CI-friendly; 12 cases covering byte layout, v1.1 compat,
  cross-segment `{{arg:N}}`) and `tests/test_v12_pipe_e2e.sh`
  (interactive e2e; 7 cases covering single-/two-/three-segment
  pipelines and the full exit-code matrix).

### Security

- Pipe functionality is implemented entirely in the runner's C code.
  Shell metacharacters in user-supplied `{{arg:N}}` values (`;`,
  `$(...)`, backticks, `>`, etc.) remain **inert** because nothing
  ever passes through `/bin/sh` — they are only byte strings inside
  a specific segment's `argv` slot.

### Known non-goals (v1.2)

- No shell redirection (`>`, `<`), chaining (`&&`, `||`, `;`),
  stderr merging (`2>&1`), variable/command substitution, or glob
  expansion. These are **permanently rejected** because they would
  re-open the injection surface that the pipe design deliberately
  avoids.
- GUI support for composing multi-segment templates is deferred to
  v1.2.1 and tracked separately.

## [1.1.0] - Unreleased

First public open-source release. Version 1.1 is a security-hardening
milestone on top of the 1.0 baseline that was developed in private.

### Added

- **Runtime program-path binding.** `cmdseal seal` resolves bare
  program names (e.g. `zip`) to an absolute path via `shutil.which`
  at seal time and bakes the result into the AEAD ciphertext. The
  runner then refuses any `$PATH` lookup.
- **`cmdseal rotate`** subcommand: generates a fresh AES-256 key,
  rewrites the AEAD ciphertext, re-signs the sealed binary and swaps
  the keychain item atomically. Non-interactive, ~1 s per runner.
- **Runner management** in the GUI: list all sealed runners with
  their keychain items, delete them (keychain entry + on-disk file
  kept in sync).
- **Template wizard** ("build a template from a working command")
  in the GUI, plus path-aware argument visualisation.
- **Preferences panel** (`⌘,`) in the GUI, backed by `QSettings`,
  persisting default output directory, filename prefix and dry-run
  timeout; the template wizard reads these defaults at init time.
- **Bilingual documentation**: `README.md` / `README.zh.md`,
  `DESIGN.md` / `DESIGN.zh.md`, `USER_GUIDE.md` /
  `USER_GUIDE.zh.md`.
- **`tests/`** directory with headless GUI tests
  (`QT_QPA_PLATFORM=offscreen`) and `test_v11_e2e.sh` end-to-end
  security validation script (7 indicators).
- **Third-party license disclosure**: `THIRD_PARTY_LICENSES.md` for
  PySide6 / Qt LGPL compliance.
- **MIT License** file (`LICENSE`).

### Security

- **#2 `execvp` → `execv`.** The generated runner no longer performs
  any runtime `PATH` resolution; the underlying program path is the
  absolute path resolved and baked in at seal time. Prevents
  `PATH`-based program substitution.
- **#3 `DYLD_*` / `LD_*` environment stripping.** `strip_dangerous_env`
  is called before `execv`, so neither the sealed binary's child
  process nor any `cmdseal`-spawned subprocess inherits dylib-
  injection variables.
- **#4 Hardened runtime.** Both the sealed runner and `cmdseal_helper`
  are signed with `codesign --options runtime` (ad-hoc identity),
  which instructs `dyld` itself to ignore `DYLD_*` variables for
  this binary even if they are somehow re-introduced.
- **Plan D AEAD.** The secret is embedded as AES-GCM ciphertext
  inside the binary; it only exists in plaintext inside the runner's
  address space for the brief window between keychain fetch and
  `execv`.
- **Keychain ACL binding.** The partition-list / ACL of the stored
  key is bound to the sealed binary's cdhash. Bitwise-identical
  copies, ad-hoc signed probes, and direct `security` calls have
  all been verified to be rejected.

### Changed

- GUI seal wizard simplified (fewer steps, clearer argument
  visualisation); README repositioned around "developer source-code
  build" as the primary distribution model.
- Repository home moved to <https://github.com/szgenle/cmdseal>
  (previous internal mirror retired).

### Documentation

- README rewritten (EN + zh) with an explicit `Security model`
  section covering what cmdseal does and does **not** protect
  against.
- `SECURITY.md` added with the vulnerability-reporting channel and
  response SLA.

### Known limitations

- Distribution is source-only. No Developer-ID-signed notarized
  `.app` is published yet; that is gated on the maintainer joining
  the Apple Developer Program (tracked via GitHub Issues).
- macOS only. Linux / Windows are explicitly out of scope because
  the security model depends on macOS keychain ACL + cdhash binding.

## [1.0.0] - Pre-release baseline (never tagged publicly)

Initial private baseline — included here for historical context only.

- AEAD-sealed runner generation (`cmdseal seal`).
- Keychain-stored AES-256 key with cdhash-bound ACL.
- Ad-hoc codesigning of the generated runner.
- First-cut PySide6 GUI with a seal wizard.
- PyInstaller `.app` packaging pipeline.

[1.2.0]: https://github.com/szgenle/cmdseal/releases/tag/v1.2.0
[1.1.0]: https://github.com/szgenle/cmdseal/releases/tag/v1.1.0
