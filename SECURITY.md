# Security Policy

> 中文版：[SECURITY.zh.md](./SECURITY.zh.md)

`cmdseal` is a macOS security tool whose entire value proposition is
preventing secret material from leaking to AI coding agents, other
processes on the same machine, and tampered copies of the sealed
binary. Security reports are therefore treated as first-class issues.

## Supported versions

Only the latest release line on `main` receives security fixes. Older
snapshots pinned from git are out of scope; please upgrade before
reporting.

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| < 1.1   | :x:                |

## Reporting a vulnerability

**Do not open a public GitHub issue for security problems.**

Please report privately via either channel:

- **Email:** `dev@szgenle.com` — include a clear title prefixed with
  `[cmdseal security]`.
- **GitHub Security Advisories:** use the *Report a vulnerability*
  button on the repository's *Security* tab
  (<https://github.com/szgenle/cmdseal/security/advisories/new>).

A useful report typically includes:

- cmdseal version / commit SHA, macOS version, Xcode CLT version.
- Minimal reproduction: the command template used to `seal`, the
  invocation that triggers the issue, and the observed vs. expected
  behaviour.
- Whether the issue leaks plaintext secrets, bypasses keychain ACL
  binding, bypasses `DYLD_*` stripping / hardened runtime, or allows
  substituting the underlying program.

## Response SLA

Best-effort targets from a solo maintainer — not a contractual SLA:

| Stage                          | Target                  |
| ------------------------------ | ----------------------- |
| Acknowledge receipt            | within 3 business days  |
| Initial triage + severity call | within 7 business days  |
| Fix or mitigation published    | within 30 days (High/Critical) |

If you have not heard back within a week, please re-send the report
(email delivery failures happen).

## Scope

In scope, broadly:

- Breaking the binding between a sealed runner's cdhash and its
  keychain-stored AES key (ACL bypass).
- Recovering secrets from a sealed binary without the corresponding
  keychain item (AEAD bypass, side channels).
- Injecting code into a sealed runner's address space before `execv`
  (e.g. via environment, `DYLD_*`, path substitution).
- Privilege escalation or persistence achieved by abusing `cmdseal`
  itself (CLI or GUI).

Out of scope:

- Attacks that require the attacker to already have code execution
  as the same user *and* interactive keychain-unlock rights — that is
  part of the documented threat model, see the
  [Security model](./README.md#security-model) section of the README.
- Social-engineering the user into running an unrelated malicious
  binary.
- Issues in upstream dependencies (PySide6, Qt, CPython, macOS
  itself) — please report those to the respective projects.

## Coordinated disclosure

We prefer coordinated disclosure. Please give us a reasonable window
(typically 30–90 days depending on severity) before publishing
details. Credit will be given in the release notes / CHANGELOG unless
you request otherwise.
