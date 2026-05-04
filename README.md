# cmdseal (PoC)

> *Capability gateways for the AI agent era.*
> *Give your AI agent the ability to call sensitive commands, without giving it the secrets.*

This is the **proof-of-concept** implementation that validates the end-to-end
security chain described in [../DESIGN.md](../DESIGN.md):

```
command template  →  generated C source  →  ad-hoc signed binary
                                                ↓
                                       Keychain ACL bound to THIS binary
```

macOS only. No GUI yet — that will be built on top of `cmdseal.py` once
the core chain is proven.

## Requirements

- macOS (tested on darwin 24+)
- `cc` (from Xcode Command Line Tools)
- `codesign`
- `/usr/bin/security`
- Python 3.8+

## Quick start

```bash
cd cmdseal

# Seal an `echo` command that takes one secret and one runtime arg.
python3 cmdseal.py \
    --output ./demo_sealed \
    --command 'echo {{secret:mypass}} {{arg:1}}'
# → prompts for the value of `mypass` (twice), then builds ./demo_sealed

# Run it:
./demo_sealed hello-from-caller
# First run will pop ONE keychain prompt — click "Always Allow".
# From then on: silent.
# Output:  <the_password_you_entered> hello-from-caller
```

## Placeholder reference

| Placeholder         | Resolved at | Source                                |
| ------------------- | ----------- | ------------------------------------- |
| `{{secret:NAME}}`   | runtime     | `cmdseal.<hash>.NAME` in Keychain     |
| `{{arg:N}}`         | runtime     | `argv[N]` of the generated binary     |
| any other token     | —           | literal, passed through unchanged     |

Placeholders must occupy a **whole argv position** — mixed tokens like
`"--pwd={{secret:x}}"` are rejected. Split them into two tokens instead:
`--pwd {{secret:x}}`.

## A realistic example (the motivating use case)

```bash
python3 cmdseal.py \
    --output ~/bin/zhmm_fetch \
    --command 'zhmm_cmd -i /Users/ws/szdoc/zhmm/zhmm.gl.gl \
               --openId olQ0e7SL_98gbj2lqV_zki-Vjxco \
               --pwd {{secret:master}} \
               --search {{arg:1}} \
               --once'
```

Then the home AI agent can invoke:

```bash
~/bin/zhmm_fetch "gmail"
```

…and the master password is never visible in the argv list, never written
to disk in plaintext, never transmitted. If the agent tries to read it
directly:

```bash
/usr/bin/security find-generic-password -s cmdseal.<hash>.master -w
# → GUI prompt. Agent cannot click "Allow". Denied.
```

## Housekeeping

```bash
# Inspect the keychain entry (metadata only):
security find-generic-password -s cmdseal.<hash>.master -g

# Remove the entry (e.g. when retiring a binary):
security delete-generic-password -s cmdseal.<hash>.master

# Inspect the binary's embedded placeholders (no secrets in there):
strings ./demo_sealed | grep cmdseal
```

## Current limitations (v1 PoC)

- **First-use prompt on the sealed binary itself.** Due to the macOS
  partition-list mechanism, the owner must click "Always Allow" once
  the first time the sealed binary runs. Subsequent invocations are
  silent, which is what the AI agent needs. Fixing this (so that no
  prompt is shown even on first use) is planned for v2.
- No registry of sealed binaries → you have to remember which service
  prefix belongs to which binary (look at `strings` or keep notes).
- No automatic cleanup of keychain entries when a binary is deleted.
- No update command (`cmdseal rotate <binary>` to change the secret
  without rebuilding) — planned.
- No argument whitelist / regex validation — planned.
- No audit log — planned.
- Side-channel hardening is not yet done: the sealed binary still uses
  `execvp` (PATH-searched) and passes secrets via argv of the target
  command, so a same-user attacker with `$PATH` write access or a
  tight `ps -E` polling loop can intercept. Planned v1.1 work.
- macOS only. Linux (`libsecret`) and Windows (DPAPI) are future work.

## Signing mode vs. enforcement strength

Verified non-interactively (see `acl_test.py`): **even under ad-hoc
signing, the Keychain ACL blocks any other caller** — `/usr/bin/security`,
a different ad-hoc signed binary, and a bytewise-identical copy of the
sealed binary all trigger a GUI prompt that an unattended AI agent
cannot dismiss.

| Signing mode                        | Flag                                                             | Enforcement  | Recommended for                   |
| ----------------------------------- | ---------------------------------------------------------------- | ------------ | --------------------------------- |
| Ad-hoc (default)                    | *(none)*                                                         | ✅ works     | Personal / single-machine use     |
| Developer ID (paid Apple program)   | `--signing-identity "Developer ID Application: Name (TEAMID)"`   | ✅ + tighter | Distributed / shared builds       |

Developer ID is optional hardening, not a prerequisite. For the
home-agent threat model that motivated `cmdseal`, ad-hoc is sufficient.

```bash
# Ad-hoc (default) is already fine for most users.
python3 cmdseal.py --output ./fetch_pwd --command '...'

# Developer ID, if you have one and want the stronger designated
# requirement on the ACL.
python3 cmdseal.py \
    --signing-identity "Developer ID Application: Jane Doe (ABCDE12345)" \
    --output ./fetch_pwd \
    --command '...'
```

See [../DESIGN.md](../DESIGN.md) §8 for the full empirical findings and
the methodology correction (earlier drafts reported a false negative
caused by the operator clicking through prompts during manual tests).
