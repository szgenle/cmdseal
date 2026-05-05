# cmdseal — Design Document

> *Capability gateways for the AI agent era.*
> *Give your AI agent the ability to call sensitive commands, without giving it the secrets.*

[中文版](./DESIGN.zh.md)

---

## 1. Why this tool exists

In the AI-agent era more and more people deploy a personal agent at home
that can read files, run local tools, and reply over IM / email while the
owner is away.

Some of those operations need **secrets** (master password for an offline
password manager, a private key, a locked archive key...). Giving those
secrets to the agent is unacceptable — a prompt injection, a logged
conversation, or a compromised channel leaks them all.

Yet we still want the agent to help. The question is:

> *How do I let the agent **invoke** a sensitive operation, without letting
> it **know** the secret that operation needs?*

`cmdseal` answers this by generating a **signed, keychain-locked,
single-purpose binary** — a capability gateway. The agent can run it; the
agent cannot read what is inside it, nor extract the secret it uses.

---

## 2. Threat model

| Actor                 | Trusted for              | Not trusted for                     |
| --------------------- | ------------------------ | ----------------------------------- |
| You (owner)           | everything               | —                                   |
| Home AI agent         | invoking programs        | reading secrets, modifying binaries |
| Network / IM / email  | transporting ciphertext  | carrying plaintext secrets          |
| Attacker with binary  | —                        | running on another machine          |

Assumptions:

- The AI agent runs in the owner's macOS login session.
- The agent can read the filesystem, run arbitrary commands, shell out to
  `security(1)`, and send files over the network.
- The agent **cannot** respond to interactive GUI prompts (no user
  present).
- Keychain is in its normal "unlocked during session" state.

Out of scope for v1:

- Attacker with root + debugger on the same machine (can ptrace the
  running binary and snoop memory).
- Malicious macOS updates or compromised Apple signing roots.
- Side-channel attacks on keychain cryptography.

---

## 3. Architecture

```
        Away                            Home machine
   ┌──────────────┐              ┌──────────────────────────┐
   │  Owner       │              │      AI agent             │
   │  (phone)     │              │  (can call programs)      │
   └──────┬───────┘              └──────────┬───────────────┘
          │ ① "Fetch password for X"        │ only `exec`, never `read`
          │──────────────IM──────────────►  │
          │                                  ▼
          │                   ┌──────────────────────────────┐
          │                   │  cmdseal-generated binary     │
          │                   │  (ad-hoc signed, ACL-bound)   │
          │                   └──────────┬───────────────────┘
          │                              │ ② SecKeychainFind...()
          │                              ▼
          │                   ┌──────────────────────────────┐
          │                   │  macOS Keychain               │
          │                   │  ACL = { this binary only }   │
          │                   └──────────┬───────────────────┘
          │                              │ ③ decrypted secret
          │                              ▼
          │                   ┌──────────────────────────────┐
          │                   │  execvp(target_cmd, argv)     │
          │                   │  stdout → encrypted archive   │
          │                   └──────────┬───────────────────┘
          │ ④ encrypted blob             │
          │◄────────────IM/email─────────┘
          ▼
   Decrypt locally on phone
   with a password that never left the owner's head
```

---

## 4. Security mechanisms

### 4.1 Secrets never live in the binary

The generated C source contains only **placeholders** (`__SECRET__NAME`)
and a **service name** (`cmdseal.<hash>.NAME`). At generation time the
actual secret is written to the macOS Keychain. `strings <binary>` reveals
the service name — useless without Keychain unlock.

### 4.2 Keychain ACL bound to this specific binary

After compiling, cmdseal:

1. Strips & ad-hoc signs the binary (`codesign -s - --force <bin>`).
2. Adds the keychain entry with the binary on the trusted app list:
   ```
   security add-generic-password \
     -a "$USER" -s "cmdseal.<hash>.NAME" \
     -w "<secret>" \
     -T "<binary_path>" \
     -U
   ```

Effect:

| Caller                               | Result                   |
| ------------------------------------ | ------------------------ |
| The generated binary itself          | ✅ silent success         |
| Any other process (incl. AI agent)   | ❌ GUI prompt → denied    |
| The same binary moved to another box | ❌ entry absent → fail    |
| A rebuilt / tampered binary          | ❌ sig mismatch → prompt  |

The key insight: the ACL check is performed by the macOS Security
framework against the *calling process's code requirements*, not just its
path. Ad-hoc signing pins the identity to a specific compiled artifact.

### 4.3 No shell in the runtime path

The generated binary uses `execvp(argv[0], argv)` with a pre-split argv
array. It never passes user input through `system()` or `/bin/sh`, so
argument values cannot break out into shell metacharacters.

### 4.4 Argument passthrough is positional only

A placeholder like `{{arg:1}}` is replaced by `argv[1]` of the invocation
and nothing else. The runtime does not expand `~`, glob, or interpolate
env vars in passthrough values.

### 4.5 Output channel (recommended usage)

The sealed command is expected to write an **encrypted artifact** (e.g.
`zip -P`, `gpg`, `age`) to a file path, and print only a short success
line to stdout. The AI agent forwards the artifact as-is; the plaintext
never appears in stdout, logs, or network frames.

### 4.6 Pipe execution (v1.2)

A sealed binary may contain **1..N segments** joined by stdout→stdin
pipes (hard cap: 8 segments). The pipeline is executed by the runner's
own C code — `pipe()`+`fork()`+`dup2()`+`waitpid()` — **never** by
`/bin/sh`. Each segment still runs through `execv()` and still passes
the v1.1 hardening checks (absolute-path requirement, `DYLD_*` / `LD_*`
stripped before fork).

Consequences:

- Shell metacharacters in `{{arg:N}}` values (`;`, `|`, `$(...)`,
  backticks, `>`, etc.) remain **inert**. They are byte strings in a
  specific segment's `argv` slot — no shell ever parses them.
- Exit-code semantics are **pipefail-equivalent**: if any segment
  exits non-zero, the sealed binary exits with the **left-most**
  failing code. All segments still run to completion, matching
  `set -o pipefail` in bash/zsh. Safety tools should fail loudly.
- Single-segment sealed binaries take a **no-`fork` fast path**. The
  plaintext blob format is byte-identical to v1.1, so existing
  binaries see zero regression.

See [research/DESIGN.pipe.md](./research/DESIGN.pipe.md) for the full
format (`TOK_PIPE = 0x03` separator) and pseudocode.

---

## 5. Placeholder language (v1)

A command template is a single shell-like string, tokenized by `shlex`:

| Placeholder         | Resolved at  | Source                               |
| ------------------- | ------------ | ------------------------------------ |
| `{{secret:NAME}}`   | Runtime      | Keychain `cmdseal.<hash>.NAME`       |
| `{{arg:N}}`         | Runtime      | `argv[N]` of the generated binary    |
| literal token       | —            | used as-is                           |

> **Pipe scoping (v1.2).** When the sealed binary is a multi-segment
> pipeline, `{{arg:N}}` numbering is **global** — the same `argv[N]`
> can be referenced from any segment, and numbering stays continuous
> across segments. Literal tokens remain local to the segment that
> contains them.

Example:

```
zhmm-cli -i /Users/ws/data.zmb \
  --account you@example.com \
  --pwd {{secret:master}} \
  -s {{arg:1}}
```

Generates a binary invoked as:

```
./zhmm_fetch "some keyword"
```

---

## 6. Generation workflow

```
cmdseal.py
  └─► read --command template
  └─► shlex split to tokens
  └─► collect distinct {{secret:NAME}} placeholders
  └─► getpass() each secret from user
  └─► generate service hash (uuid4 short)
  └─► render wrapper_template.c → build/wrapper.c
  └─► cc -O2 -framework Security -framework CoreFoundation
         -o <output> build/wrapper.c
  └─► codesign -s - --force --timestamp=none <output>
  └─► for each secret:
         security add-generic-password -U
             -s cmdseal.<hash>.NAME -a $USER -w <value>
             -T <output>
  └─► print summary (service name, install path, usage hint)
```

---

## 7. Non-goals (v1)

- Cross-platform. macOS only. Linux/Windows can come later with
  `libsecret` / DPAPI adapters.
- GUI. The GUI is a thin front-end that shells out to `cmdseal.py`;
  building it is a v2 concern once the core flow is proven.
- Automatic argument sanitization. Users are expected to write sealed
  commands that treat `{{arg:N}}` values as untrusted data (quoted in
  argv positions, not used to build paths).

---

## 8. Empirical findings from the v1 PoC

The PoC was exercised end-to-end on darwin 24+ (macOS). Results below
are from a **non-interactive negative-test harness** (see
`cmdseal/acl_test.py`): every candidate caller runs under a 5-second
hard timeout so that a GUI keychain prompt — which an unattended AI
would never dismiss — manifests as a timeout rather than as a
"success".

> ⚠️ An earlier draft of this document reported that ACL enforcement
> was broken under ad-hoc signing. That conclusion was wrong. The
> operator had been clicking "Allow" on every prompt during manual
> testing, masking the fact that each call was in fact being prompted.
> After switching to the non-interactive harness the real picture
> emerged — and it is much better.

✅ **Generation pipeline works.** `cmdseal.py` parses the template,
renders the C source, compiles with `cc -framework Security`, ad-hoc
signs with `codesign -s -`, and stores the secret via the dedicated
`cmdseal_helper` (built with `SecAccessCreate` so `/usr/bin/security`
is deliberately absent from the ACL's trusted-app list).

✅ **ACL enforcement is real — even under ad-hoc signing.** Against a
fresh keychain item on which no caller has ever been authorized:

| Attacker scenario                                  | Result (5 s timeout) |
| -------------------------------------------------- | -------------------- |
| `/usr/bin/security find-generic-password -w`       | ⏸ timed out — prompt shown, no access |
| A *different* ad-hoc signed binary calling the API | ⏸ timed out — prompt shown, no access |
| A bytewise-identical *copy* of the sealed binary   | ⏸ timed out — prompt shown, no access |

All three non-authorized callers triggered a GUI confirmation prompt.
An AI agent running headlessly in the owner's session has no way to
click that prompt. **The capability-gateway property holds.**

### Known UX issue: first-use prompt on the sealed binary itself

The first invocation of the sealed binary *also* triggers a prompt
(the user must click "Always Allow" once). This is caused by the
**partition-list** mechanism introduced in macOS Sierra: items created
via `SecKeychainItemCreateFromContent` receive an empty partition
list, so even a caller on the ACL's trusted-app list gets prompted
until the user blesses the combination once.

This is a UX wart, not a security hole:

- The prompt happens **once** per (keychain item, caller binary) pair.
  After "Always Allow", subsequent invocations are silent — which is
  what the AI agent needs.
- The partition-list prompt still blocks *non-trusted* callers (they
  additionally fail the ACL check, which is evaluated first).
- Properly configuring the partition list requires `SecKeychainSet
  GenericPasswordPartitionList` (or the equivalent private API used
  by `/usr/bin/security -T`). v2 should do this at item-creation time
  in `cmdseal_helper` to eliminate the first-use prompt.

### Threat-model status after v1

Against the stated threat model — *AI can `exec`, AI cannot `read
secret`* — the PoC **meets the bar** on ad-hoc signing, provided the
owner has performed the one-time "Always Allow" authorization for the
sealed binary during setup.

### Optional hardening: Developer ID signing

A paid Developer ID certificate (Apple Developer Program, USD 99/yr)
supplies a stronger designated requirement on the ACL and is usable
via:

```bash
python3 cmdseal.py \
    --signing-identity "Developer ID Application: Jane Doe (ABCDE12345)" \
    ...
```

With Developer ID the designated requirement pins Team ID + cdhash,
which narrows the set of binaries that could theoretically pass ACL
checks in edge cases (e.g. a Gatekeeper-exempt privileged context).
For the common home-agent threat model ad-hoc signing is sufficient;
Developer ID is recommended only for distributed / shared builds.

### Open questions remaining after v1

1. Set the partition list at creation time so the first-use prompt
   disappears for the sealed binary (known private-API path, to
   validate on macOS 14+/15+).
2. How to invalidate all keychain entries when a binary is deleted —
   needs a registry file under `~/Library/Application Support/cmdseal/`.
3. Side-channel hardening for the sealed binary itself: drop PATH
   lookup (`execv` + absolute path enforcement), scrub environment,
   enable hardened runtime to block `DYLD_INSERT_LIBRARIES`, pass
   secrets via pipe-fd rather than argv so `ps -E` cannot race.
4. Should v2 offer an alternative vault (encrypted file + Secure
   Enclave unlock) for users who accept a user-presence requirement
   in exchange for stronger enforcement?

---

## 9. Appendix: 中文要点速览

- **目标**：让家里的 AI 智能体在你外出时「能调用」敏感操作（如从离线密码管理器取某条密码），但「读不到」底层秘密。
- **核心机制**：
  1. 秘密不写进二进制，写进 macOS Keychain。
  2. Keychain 条目的 ACL 绑定到**这个经过 ad-hoc 签名的二进制**。
  3. AI 调用二进制 → 静默拿到密码 → 执行命令 → 输出密文压缩包。
  4. AI 自己去读 Keychain → 弹 GUI 弹窗 → 没人点 → 失败。
- **AI 能力**：`exec` ✔  `read secret` ✘
- **网络传输**：只有密文。
- **解密方**：只有你的手机 + 只在你脑子里的密码。
