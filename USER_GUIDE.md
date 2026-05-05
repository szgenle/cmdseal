# cmdseal User Guide

> **Complete operating manual for end users** — from getting started to advanced usage.

---

## Table of Contents

- [1. Quick Start](#1-quick-start)
  - [1.1 GUI Users (Recommended)](#11-gui-users-recommended)
  - [1.2 CLI Users (Advanced)](#12-cli-users-advanced)
- [2. GUI Seal Wizard in Depth](#2-gui-seal-wizard-in-depth)
  - [2.1 Launching the Wizard](#21-launching-the-wizard)
  - [2.2 Step 1: Command Template](#22-step-1-command-template)
  - [2.3 Step 2: Secret Collection](#23-step-2-secret-collection)
  - [2.4 Step 3: Options](#24-step-3-options)
  - [2.5 Step 4: Execute and Preview](#25-step-4-execute-and-preview)
  - [2.6 Build Template from Command (Simplified Entry)](#26-build-template-from-command-simplified-entry)
- [3. Runner Management](#3-runner-management)
  - [3.1 View Runner List](#31-view-runner-list)
  - [3.2 Edit Template (Key Rotation)](#32-edit-template-key-rotation)
  - [3.3 Delete a Runner](#33-delete-a-runner)
- [4. CLI Reference](#4-cli-reference)
  - [4.1 seal — Seal a Command](#41-seal--seal-a-command)
  - [4.2 rotate — Rotate the Key](#42-rotate--rotate-the-key)
  - [4.3 list — List Runners](#43-list--list-runners)
  - [4.4 edit-template — Edit Template](#44-edit-template--edit-template)
- [5. Placeholder Syntax](#5-placeholder-syntax)
  - [5.1 Basic Rules](#51-basic-rules)
  - [5.2 Example Scenarios](#52-example-scenarios)
  - [5.3 Common Mistakes](#53-common-mistakes)
- [6. Security Model](#6-security-model)
  - [6.1 What Is Protected](#61-what-is-protected)
  - [6.2 What Is Not Protected](#62-what-is-not-protected)
  - [6.3 First-Run Dialog](#63-first-run-dialog)
- [7. Daily Maintenance](#7-daily-maintenance)
  - [7.1 Inspect Keychain Entries](#71-inspect-keychain-entries)
  - [7.2 Retire Old Runners](#72-retire-old-runners)
  - [7.3 Inspect Binary Metadata](#73-inspect-binary-metadata)
- [8. Troubleshooting](#8-troubleshooting)
  - [8.1 First-Run Dialog Was Denied](#81-first-run-dialog-was-denied)
  - [8.2 Program Not Found at Runtime](#82-program-not-found-at-runtime)
  - [8.3 GUI Fails to Launch](#83-gui-fails-to-launch)
- [9. Best Practices](#9-best-practices)
  - [9.1 Naming Conventions](#91-naming-conventions)
  - [9.2 Key Rotation Strategy](#92-key-rotation-strategy)
  - [9.3 Team Collaboration](#93-team-collaboration)

---

## 1. Quick Start

### 1.1 GUI Users (Recommended)

**Who this is for**: everyday users and anyone who prefers not to touch the command line.

```bash
# 1. Clone the repository
git clone https://github.com/szgenle/cmdseal.git
cd cmdseal

# 2. Install dependencies
make sync

# 3. Build the GUI app
make app

# 4. Launch the app
open dist/cmdseal.app
```

✅ **Done!** The seal wizard GUI should now appear.

> 🔰 **First-time tip:** From the main window click **“Build template from command…”** (see [§ 2.6](#26-build-template-from-command-simplified-entry)).
> Follow the top-of-page example `echo hello world` end-to-end once — get comfortable with the runtime-argument concept, then come back to the more security-heavy seal wizard.

---

### 1.2 CLI Users (Advanced)

**Who this is for**: developers, CI/CD pipelines, and automation scripts.

```bash
# 1. Clone the repository
git clone https://github.com/szgenle/cmdseal.git
cd cmdseal

# 2. Seal a command (you will be prompted for the secret interactively)
python3 cmdseal.py seal \
    --command 'zip -j -P {{secret:zippw}} {{arg:1}} {{arg:2}}' \
    --output ./my_sealed_zip

# 3. Use the sealed binary
./my_sealed_zip /tmp/output.zip /path/to/secret_file.txt
```

> 💡 **Tip**: GUI users should run `make app`; the CLI is meant for scripting, CI pipelines, and auditing.

---

## 2. GUI Seal Wizard in Depth

### 2.1 Launching the Wizard

```bash
# Development mode (requires a Python environment)
make run

# Or launch the built .app
open dist/cmdseal.app
```

---

### 2.2 Step 1: Command Template

**Goal**: enter the command template you want to seal.

**Supported syntax**:

| Type | Example | Description |
|------|---------|-------------|
| **Literal password** | `zip -j -P mypassword` | Written verbatim into the command (simple, not recommended for high-security cases). |
| **Secret placeholder** | `{{secret:zippw}}` | Collected at seal time, never exposed in shell history. |
| **Runtime argument** | `{{arg:1}}` `{{arg:2}}` | Supplied by the caller at runtime. |

**Examples**:

```bash
# Example 1: Literal password (simple case)
zip -j -P mypassword {{arg:1}} {{arg:2}}

# Example 2: Secret placeholder (recommended)
zhmm-cli --pwd {{secret:master}} -s {{arg:1}}

# Example 3: Mixed usage
openssl enc -aes-256-cbc -k {{secret:key}} -in {{arg:1}} -out {{arg:2}}
```

**Multi-segment pipeline (v1.2.1)**:

The Command Template page lets you click **➕ Add pipe segment** to reveal
another editor, up to 8 segments. At runtime the runner wires up
`pipe()` / `fork()` / `dup2()` itself so stdout of segment N feeds stdin
of segment N+1 **without ever invoking a shell**.

- `{{arg:N}}` is numbered globally across all segments: put
  `{{arg:1}}` in segment 1 and `{{arg:2}}` in segment 2, then invoke
  `./bin a b` at runtime.
- Exit-code policy is pipefail-equivalent (**left-most failure wins**).
- The footer summary shows `segments=N/8`, total tokens across all
  segments, the deduplicated secret names, and the global arg set —
  a paper-review of your design.
- The first segment cannot be removed; other segments have a `×`
  button at their header. Empty segments are dropped automatically
  before being passed to the CLI.

**Smart warnings**:

- ⚠️ Unwrapped `secret:` / `arg:` detected → use `{{secret:NAME}}` or `{{arg:N}}`.
- ℹ️ First token is not an absolute path → it will be resolved to an absolute path at seal time.
- ⚠️ First token is a placeholder → make sure an absolute path is passed in at runtime.

> 💡 **Want Tab path completion?** The seal wizard does not provide it; if you are a beginner or do not need `{{secret:}}`,
> use the main window’s “Build template from command…” entry instead (see [§ 2.6](#26-build-template-from-command-simplified-entry)).

---

### 2.3 Step 2: Secret Collection

**When it appears**: only when the command template contains `{{secret:NAME}}`.

**Goal**: provide a real value for every secret placeholder.

**Features**:
- 🔒 Password fields are hidden by default (click “Show” to reveal).
- ✅ Values are required; the “Next” button stays disabled until every field is filled.
- 🚀 If there is no `{{secret:*}}`, this page is skipped automatically.

**Example**:

Given this command:
```bash
zhmm-cli --pwd {{secret:master}} --api-key {{secret:apikey}}
```

The page will show two input fields:
1. `master` — enter the master password
2. `apikey` — enter the API key

---

### 2.4 Step 3: Options

**Fields you fill in**:

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| **Output path** | ✅ | Path of the generated binary | `~/bin/my_runner` |
| **Label** | ❌ | Friendly label | `Prod ZIP encryption` |
| **Signing identity** | ❌ | Developer ID (optional) | `Developer ID Application: ...` |

**Defaults**:
- No label → the output filename is used.
- No signing identity → an ad-hoc signature is used (secure enough).

---

### 2.5 Step 4: Execute and Preview

**What you see**:

1. **Command preview** — the final sealed command (with absolute paths resolved).
2. **Secret list** — collected secrets (values hidden).
3. **Runtime arguments** — how many arguments the caller must pass.

**Actions**:
- Click **“Execute”** → runs `cmdseal.py seal` in the background.
- A progress bar shows the build status.
- On success, the result message and output location are displayed.

---

### 2.6 Build Template from Command (Simplified Entry)

**Who this is for**:
- First-time users who are not yet comfortable with `{{secret:}}` / `{{arg:}}` syntax.
- Users who already have a working command and just want to point-and-click which arguments should become runtime parameters.

**Entry point**: main window → **“Build template from command…”** button.

The wizard has 4 pages and is more approachable than the seal wizard in § 2.2: write and successfully run the command first, then pick the runtime arguments.

---

#### 2.6.1 Step 1: Command Input + Dry Run

**Always-visible example**: `echo hello world`. Click “Fill example” to insert it, then “Dry run” to walk through the full flow.

> ⚠ **No shell involved**: every segment is executed directly with `execv`; environment variables `$VAR`, redirection `>`, and globs `*` are not expanded. Wrap with `sh -c` yourself if you need shell features.
>
> ➕ **Multi-segment pipeline (v1.2.2)**: to chain `cmd1 | cmd2 | cmd3`, click “➕ Add pipe segment” rather than typing `|` inside a single segment (the pipeline is not mediated by the shell and matches exactly what the sealed runner will execute at runtime). Hard cap is 8 segments.

**Validation rules**:
- Static check (per segment): `shlex`-parseable, and the first token is either on `PATH` or an absolute executable file.
- Dynamic check: you **must** click “Dry run entire pipeline” and see exit code = 0 for **every** segment to proceed.
- Multi-segment dry run chains the processes via `QProcess.setStandardOutputProcess` (`proc[i].stdout → proc[i+1].stdin`), which is byte-equivalent to what the v1.2 runner does at runtime; pipefail semantics — any failed segment fails the whole verification.
- Dry run has a 10-second timeout; any edit to any segment immediately invalidates the “verified” state.

**Tab path completion** (bash-style):

| Situation | Behavior |
|-----------|----------|
| Token before cursor starts with `/`, `~`, `./`, or `../` | Triggers path completion |
| Single match | Completes directly; directories gain a trailing `/` |
| Multiple matches | Completes to the longest common prefix; press Tab again to list candidates |
| Non-path token | Tab moves focus to the next widget (normal form behavior) |

The `~/` prefix is preserved (it is not expanded to an absolute `$HOME` path in the input).

---

#### 2.6.2 Step 2: Pick Runtime Arguments

Each token of the command is shown as a clickable “chip”:

- White background = literal (embedded into the sealed artifact).
- Blue background = runtime argument (numbered `{{arg:1}}`, `{{arg:2}}`, … in order of appearance).
- Unselected tokens are protected via `shlex.quote`, so literals with spaces or special characters stay intact.
- Selecting the first token triggers a warning: an absolute executable path must be supplied at runtime.

**Multi-segment (v1.2.2)**: each segment gets its own chip row, but `{{arg:N}}` numbering increments **globally** across all segments. For example, if segment 1 selects 2 tokens, the first selected token in segment 2 becomes `{{arg:3}}`; at runtime arguments are dispatched across segments in the same `seal_xxx arg1 arg2 arg3 …` order. This strategy aligns with the seal wizard’s `_scan_placeholders_many` in advanced mode.

Below, the final template is rendered per segment:

```text
seg 1: /bin/echo {{arg:1}}
seg 2: /usr/bin/tr a-z A-Z
seg 3: /usr/bin/zip {{arg:2}} -
```

---

#### 2.6.3 Step 3: Save Location

| Field | Default | Description |
|-------|---------|-------------|
| **Output path** | `~/cmdseal/bin/seal_<original command name>` | The directory is created on first use; the `seal_` prefix distinguishes it from the original command (matching the demo’s `seal_zip`). |
| **Label** | empty | Auto-generated from the output filename when left empty. |
| **Keychain account** | `$USER` | The account that owns the AEAD key. |

To invoke the runner globally, click “Browse…” and manually choose something like `/usr/local/bin/seal_xxx` (writing to that path may require sudo).

---

#### 2.6.4 Step 4: Execute

After clicking **“Execute”**, the wizard invokes `cmdseal.py seal` in the background and streams the log to the page. When it finishes:

```bash
# Verify the artifact
~/cmdseal/bin/seal_echo hello world   # → prints hello world

# Refresh the Runner Management window — the new seal_echo entry appears
```

> 💡 Difference vs. § 2: this entry never exposes `{{secret:}}`. If you need secret collection (to keep passwords out of history), go back to the seal wizard in [§ 2](#2-gui-seal-wizard-in-depth).

---

## 3. Runner Management

### 3.1 View Runner List

**Entry point**: main window → “Manage runners…”

**Features**:
- 📋 Table view of every sealed runner.
- 🔍 Four columns:
  - **Label** — the friendly label.
  - **Service** — the keychain service name.
  - **Template** — the command template (positional arguments are shown as `***`).
  - **Created** — creation timestamp.

**Actions**:
- Click “Refresh” to re-scan the keychain.
- Right-click a runner to open the context menu.

---

### 3.2 Edit Template (Key Rotation)

**When to use**:
- You want to rotate the key without rebuilding the binary from scratch.
- You want to tweak the command template.

**Steps**:

1. Open the Runner Management window.
2. Right-click the target runner.
3. Choose **“Edit template…”**.
4. Enter the new command template.
5. If there are `{{secret:*}}` placeholders, you will be prompted to re-enter their values.
6. Click “Save” → everything below happens automatically:
   - ✅ Recompile the binary.
   - ✅ Generate a new key K.
   - ✅ Remove the old service.
   - ✅ Rotate the cdhash + ACL.

**Benefits**:
- 🚀 No user interaction required; takes roughly 1 second.
- 🔒 Atomic operation, no intermediate state.
- ✅ Zero authorization dialogs (the operation runs as the owner).

---

### 3.3 Delete a Runner

**Steps**:

1. Open the Runner Management window.
2. Right-click the target runner.
3. Choose **“Delete…”**.
4. Confirm the deletion.

**Cascaded cleanup**:
- ✅ The keychain entry (`cmdseal.<hash>.K`) is removed.
- ✅ The binary on disk is removed.
- ⚠️ Make sure to back up important data before confirming.

---

## 4. CLI Reference

### 4.1 seal — Seal a Command

**Basic usage**:

```bash
python3 cmdseal.py seal \
    --command 'COMMAND_TEMPLATE' \
    --output OUTPUT_PATH \
    [--label LABEL] \
    [--user USERNAME] \
    [--sign IDENTITY]
```

**Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--command` | ✅ | Command template (may contain placeholders). **May be passed multiple times** to build a pipeline (v1.2). |
| `--output` | ✅ | Path of the output binary. |
| `--label` | ❌ | Friendly label (default: output filename). |
| `--user` | ❌ | Keychain owner (default: current user). |
| `--sign` | ❌ | Signing identity (default: ad-hoc). |

**Examples**:

```bash
# Example 1: Basic seal
python3 cmdseal.py seal \
    --command 'zip -j -P {{secret:zippw}} {{arg:1}} {{arg:2}}' \
    --output ./seal_zip

# Example 2: With label and explicit user
python3 cmdseal.py seal \
    --command 'openssl enc -aes-256-cbc -k {{secret:key}} -in {{arg:1}}' \
    --output ./encrypt_file \
    --label "Prod encryption tool" \
    --user $(whoami)

# Example 3: Developer ID signing
python3 cmdseal.py seal \
    --command 'my-command {{arg:1}}' \
    --output ./my_runner \
    --sign "Developer ID Application: Your Name (TEAM_ID)"

# Example 4: Multi-segment pipeline (v1.2) — stdout→stdin between
# segments. Pass --command once per segment (up to 8 segments). The
# runner implements the pipeline in C — no shell is ever involved.
# {{arg:N}} numbering is global across all segments.
python3 cmdseal.py seal \
    --command '/usr/local/bin/zhmm_cmd -s {{arg:1}} --once' \
    --command '/usr/bin/zip query_result.zip -' \
    --output ./zhmm_pack

# The sealed binary exits with the LEFT-MOST failing segment's code
# (pipefail-equivalent). All segments still run to completion.
./zhmm_pack csj
```

---

### 4.2 rotate — Rotate the Key

**Purpose**: generate a new key without rebuilding the template.

```bash
python3 cmdseal.py rotate ./seal_zip
```

**What it does**:
1. Generates a fresh AES-256 key.
2. Rewrites the AEAD ciphertext.
3. Re-signs the binary.
4. Atomically replaces the keychain entry.

**Characteristics**:
- ⚡ Finishes in roughly 1 second.
- 🔇 Completely silent — no user interaction required.
- 🔒 Atomic operation, no intermediate state.

---

### 4.3 list — List Runners

**Basic usage**:

```bash
# Tabular output
python3 cmdseal.py list

# JSON output (suitable for scripting)
python3 cmdseal.py list --json
```

**Sample output**:

```
Label              Service                          Template
────────────────── ──────────────────────────────── ─────────────────────────
Prod encryption    cmdseal.a1b2c3.K                 openssl enc -aes-256-cbc -k *** -in {{arg:1}}
ZIP encryption     cmdseal.d4e5f6.K                 zip -j -P {{secret:zippw}} {{arg:1}} {{arg:2}}
```

**Column meanings**:
- **Label** — friendly label.
- **Service** — keychain service name.
- **Template** — command template (positional arguments masked as `***`).

---

### 4.4 edit-template — Edit Template

**Purpose**: CLI equivalent of the GUI “Edit template…” action.
Rewrites the sealed binary in place with a new command template,
rotates the keychain key `K`, and preserves the runner's label,
output path and secret-name set.

```bash
python3 cmdseal.py edit-template \
    --service cmdseal.<12hex>.K \
    --command 'NEW_COMMAND'
```

**Required parameters**:

| Parameter | Description |
|-----------|-------------|
| `--service` | Keychain service name of the runner to edit. Find it via `cmdseal.py list`. |
| `--command` | New command template. Pass multiple times to form a pipeline (max 8 segments, same semantics as `seal`). |

**Optional parameters**:

| Parameter | Description |
|-----------|-------------|
| `--user` | Keychain account name (default: `$USER`; auto-overridden by the old item's account when found). |
| `--secrets-from-stdin` | Read `NAME=VALUE` lines from stdin (for scripting / GUI front-ends). |
| `--template`, `--no-sign`, `--signing-identity`, `--keep-source` | Same meaning as in `seal`. |

**Constraints**:

- The new template's `{{secret:NAME}}` set **must equal** the original
  set. To add or remove secrets, delete and re-seal instead (AEAD is
  non-reversible, so old secret values cannot be re-applied to a
  different set of names).
- Legacy items (those without `kSecAttrComment` metadata) are rejected.
  They must be deleted and re-created via `cmdseal seal`.

**Post-conditions**:

- The on-disk binary at the preserved `output_path` is overwritten.
- A fresh `K` (and therefore a fresh keychain service name) replaces
  the old one. The first run of the rebuilt binary will trigger one
  macOS mixed-authorization dialog (new cdhash → new partition list),
  same as `rotate`.

**Example** — simple one-liner:

```bash
python3 cmdseal.py edit-template \
    --service cmdseal.1e742ffc7243.K \
    --command '/bin/echo world'
```

**Example** — with secrets (via stdin):

```bash
printf 'newzippw=s3cret\n' | python3 cmdseal.py edit-template \
    --service cmdseal.ab12cd34ef56.K \
    --command 'zip -j -P {{secret:newzippw}} {{arg:1}} {{arg:2}}' \
    --secrets-from-stdin
```

**Example** — change a pipeline runner:

```bash
python3 cmdseal.py edit-template \
    --service cmdseal.ab12cd34ef56.K \
    --command '/bin/echo hello' \
    --command '/usr/bin/tr a-z A-Z'
```

---

## 5. Placeholder Syntax

### 5.1 Basic Rules

**A placeholder must occupy a standalone argv slot**:

```bash
# ✅ Correct: standalone token
--pwd {{secret:mypass}}

# ❌ Wrong: glued into another token (rejected)
--pwd={{secret:mypass}}

# ✅ Correct: split into two tokens
--pwd {{secret:mypass}}
```

**Placeholder types**:

| Placeholder | Resolved at | Source |
|-------------|-------------|--------|
| `{{secret:NAME}}` | Seal time | Interactive prompt; embedded inside the AEAD ciphertext. |
| `{{arg:N}}` | Runtime | `argv[N]` of the generated binary. |
| Any other token | — | Passed through verbatim. |

---

### 5.2 Example Scenarios

**Scenario 1: A password-manager CLI tool**

```bash
zhmm-cli --pwd {{secret:master}} --search {{arg:1}}
```

At runtime:
```bash
./sealed_runner "search keyword"
# The master password is already embedded at seal time; nothing to pass.
```

---

**Scenario 2: File encryption / decryption**

```bash
openssl enc -aes-256-cbc -k {{secret:enc_key}} -in {{arg:1}} -out {{arg:2}}
```

At runtime:
```bash
./sealed_runner /path/to/input.txt /path/to/output.enc
```

---

**Scenario 3: Batch operations (literal password)**

```bash
# Simple case: password is not sensitive
zip -j -P mypassword {{arg:1}} {{arg:2}}
```

At runtime:
```bash
./sealed_runner /tmp/output.zip /path/to/file.txt
```

---

### 5.3 Common Mistakes

**Mistake 1: Writing placeholder tokens without braces**

```bash
# ❌ Wrong
zhmm-cli --pwd secret:master

# ✅ Correct
zhmm-cli --pwd {{secret:master}}
```

**Mistake 2: Glued tokens**

```bash
# ❌ Wrong
--api-key={{secret:key}}

# ✅ Correct
--api-key {{secret:key}}
```

**Mistake 3: `arg` indices start at 0**

```bash
# ❌ Wrong: there is no {{arg:0}}
my-command {{arg:0}} {{arg:1}}

# ✅ Correct: indices start at 1
my-command {{arg:1}} {{arg:2}}
```

---

## 6. Security Model

### 6.1 What Is Protected

✅ **cmdseal protects you from**:

1. **Secret exfiltration via argv or `ps`**
   - Secrets are embedded as AEAD ciphertext inside the binary.
   - They are decrypted only briefly in memory (keychain fetch → `execv`).

2. **Other processes reading the keychain entry**
   - The macOS ACL is bound to the exact binary cdhash.
   - Verified to block: `/usr/bin/security`, ad-hoc-signed probes, and bit-identical copies.

3. **PATH-based program substitution**
   - The runner uses `execv` with the absolute path captured at seal time.
   - No runtime `$PATH` lookup.

4. **Dylib injection via environment variables**
   - The runner strips `DYLD_*` and `LD_*`.
   - The binary is signed with `codesign --options runtime`.

---

### 6.2 What Is Not Protected

❌ **cmdseal does NOT protect you from**:

- **A root attacker** — can read any process memory and any keychain.
- **Arbitrary code execution as the same user** — can debug / dump the running binary.
- **Tampering with the build machine prior to seal time.**
- **Side channels in the target command** — e.g. `zip` itself writing a log.
- **Any attack on Linux or Windows.**

> ⚠️ **Important**: cmdseal is a **capability gateway**, not a vault. Be honest about your threat model.

---

### 6.3 First-Run Dialog

**When it appears**: the first time a freshly generated binary is run.

**Dialog contents**:
- Login password field.
- “Always Allow” button.

**Why it is needed**:
- The macOS partition-list handshake.
- Binds the keychain entry to this binary’s cdhash.

**Frequency**:
- Once per sealed binary, per user machine — **exactly once**.
- Every subsequent run is completely silent and takes milliseconds.

---

## 7. Daily Maintenance

### 7.1 Inspect Keychain Entries

```bash
# Show metadata (the secret value is not shown)
security find-generic-password -s cmdseal.<hash>.K

# Sample output
keychain: "/Users/ws/Library/Keychains/login.keychain-db"
version: 512
class: "genp"
attributes:
    0x00000007 <blob>="cmdseal.a1b2c3.K"
    "cdhash"<blob>=<SHA256 hash of binary>
```

---

### 7.2 Retire Old Runners

**Option 1: GUI deletion** (recommended)
1. Open the Runner Management window.
2. Right-click → “Delete…”.
3. Keychain entry and binary are cleaned up automatically.

**Option 2: Manual cleanup**

```bash
# 1. Remove the keychain entry
security delete-generic-password -s cmdseal.<hash>.K

# 2. Remove the binary file
rm /path/to/sealed_binary
```

---

### 7.3 Inspect Binary Metadata

```bash
# Show embedded metadata (no secrets are visible)
strings ./seal_zip | grep cmdseal

# Sample output
cmdseal.a1b2c3.K
{"label":"Prod encryption tool","created":"2026-05-05T10:30:00"}
```

---

## 8. Troubleshooting

### 8.1 First-Run Dialog Was Denied

**Symptom**: running the sealed binary reports “keychain access denied”.

**Cause**: “Deny” was clicked instead of “Always Allow” on the first run.

**Fix**:

```bash
# 1. Remove the stale keychain entry
security delete-generic-password -s cmdseal.<hash>.K

# 2. Run the binary again
./sealed_binary arg1 arg2

# 3. This time click "Always Allow"
```

---

### 8.2 Program Not Found at Runtime

**Symptom**: `No such file or directory` or `command not found`.

**Cause**: the first token was not resolved to an absolute path at seal time.

**Fix**:

```bash
# Check the seal-time output
python3 cmdseal.py seal --command 'my-command {{arg:1}}' --output ./runner
# You should see: resolved 'my-command' -> '/usr/local/bin/my-command'

# If you do not, make sure the program is on PATH
which my-command
# Or use an absolute path explicitly
python3 cmdseal.py seal --command '/usr/local/bin/my-command {{arg:1}}' --output ./runner
```

---

### 8.3 GUI Fails to Launch

**Symptom**: `make run` or `open dist/cmdseal.app` produces nothing.

**Diagnosis**:

```bash
# 1. Check that PySide6 is installed
uv run python -c "import PySide6; print(PySide6.__version__)"

# 2. Reinstall dependencies
make sync

# 3. Rebuild the .app
make clean
make app

# 4. Check logs
cat ~/Library/Logs/cmdseal.app.log 2>/dev/null || echo "no log file"
```

---

## 9. Best Practices

### 9.1 Naming Conventions

**Label naming**:

```
{env}_{purpose}_{tool}

Examples:
- prod_zip_encrypt_quick_backup
- dev_api_test_scratch_tool
- test_data_mask_batch
```

**Output filename**:

```
seal_{tool}_{env}

Examples:
- seal_zip_prod
- seal_encrypt_dev
- seal_decrypt_test
```

---

### 9.2 Key Rotation Strategy

**Suggested cadence**:

| Scenario | Frequency | Method |
|----------|-----------|--------|
| Production | Every 90 days | GUI: right-click → Edit template / CLI: `rotate` |
| Staging / testing | Every 30 days | Same as above |
| Incident response | Immediately | Same as above |

**Rotation checklist**:

- [ ] Notify every consumer of the runner.
- [ ] Schedule the rotation during a low-traffic window.
- [ ] Verify the rotated binary still works as expected.
- [ ] Update documentation with the new runner information.

---

### 9.3 Team Collaboration

**Scenario**: multiple developers need to seal the same command template.

**Option 1: Shared template file**

```bash
# 1. Create a template file (command_template.txt)
zhmm-cli --pwd {{secret:master}} --search {{arg:1}}

# 2. Each teammate seals locally
python3 cmdseal.py seal \
    --command "$(cat command_template.txt)" \
    --output ./my_runner

# 3. Each teammate gets their own binary and key
```

**Option 2: CI/CD integration**

```yaml
# .github/workflows/seal.yml
name: Seal Command
on:
  push:
    paths:
      - 'command_template.txt'

jobs:
  seal:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - run: |
          python3 cmdseal.py seal \
            --command "$(cat command_template.txt)" \
            --output ./sealed_runner
      - uses: actions/upload-artifact@v3
        with:
          name: sealed-runner
          path: ./sealed_runner
```

> ⚠️ **Note**: binaries generated on different machines are distinct (bound by cdhash) and cannot be shared across machines.

---

## Appendix

### A. Full Command Reference

```bash
# Seal
python3 cmdseal.py seal --command CMD --output PATH [--label LABEL] [--user USER] [--sign IDENTITY]

# Rotate the key
python3 cmdseal.py rotate BINARY

# List runners
python3 cmdseal.py list [--json]

# Edit template (see §4.4 for details)
python3 cmdseal.py edit-template --service SERVICE --command CMD

# Build the GUI
make app

# Run the GUI
make run
```

### B. File Layout

```
cmdseal/
├── cmdseal.py              # CLI entry point
├── runner_aead_template.c  # Runner template (C code)
├── gui/                    # GUI module
│   ├── main_window.py      # Main window
│   ├── seal_wizard.py      # Seal wizard
│   ├── runner_list.py      # Runner list
│   └── backend.py          # Backend logic
├── demo/                   # Examples
├── tests/                  # Tests
└── local/                  # Personal config (not committed)
```

### C. Related Documents

- [README.md](../README.md) — project overview.
- [DESIGN.md](../DESIGN.md) — design document.
- [LICENSE](../LICENSE) — MIT license.

---

**Document version**: v1.1  
**Last updated**: 2026-05-05  
**Maintainer**: szgenle
