/*
 * cmdseal wrapper template
 *
 * This file is a TEMPLATE. The generator (cmdseal.py) locates the
 * block-comment markers of the form @@NAME@@ and substitutes in
 * project-specific values, then compiles the result into a
 * capability-gated executable.
 *
 * Runtime behavior:
 *   1. Walk the embedded token array.
 *   2. For secret tokens, fetch the value from the macOS Keychain
 *      via the Security framework. The Keychain ACL was set at
 *      generation time to admit only THIS signed binary.
 *   3. For positional-arg tokens, substitute argv[N] of the caller.
 *   4. Build a final argv and execvp() the target command.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <Security/Security.h>

/* ============================================================
 * BEGIN generator-filled section
 * ============================================================ */

/* Service name prefix; each secret lives at "<SERVICE_PREFIX>.<NAME>". */
static const char *SERVICE_PREFIX = /* @@SERVICE_PREFIX@@ */ "cmdseal.example";

/* Keychain account = current user's login name at generation time. */
static const char *KC_ACCOUNT    = /* @@KC_ACCOUNT@@ */ "unknown";

/* Token array template. NULL terminates.
 *
 * A token is one of:
 *   "literal"              -> used verbatim
 *   "\x01secret:NAME"      -> fetched from keychain (prefix byte 0x01)
 *   "\x02arg:N"            -> replaced by argv[N] of this binary (prefix 0x02)
 */
static const char *TOKENS[] = /* @@TOKENS@@ */ {
    "echo",
    "\x01secret:demo",
    "\x02arg:1",
    NULL
};

/* Human-readable label shown on keychain prompts (unused silently when
 * ACL matches, but shown to the user if ACL is violated). */
static const char *LABEL = /* @@LABEL@@ */ "cmdseal sealed command";

/* ============================================================
 * END generator-filled section
 * ============================================================ */

#define TOK_SECRET 0x01
#define TOK_ARG    0x02

static void die(const char *msg, int rc) {
    fprintf(stderr, "cmdseal: %s\n", msg);
    exit(rc);
}

/* Fetch a secret from the keychain. Returns malloc'd null-terminated
 * string on success, NULL on failure. */
static char *fetch_secret(const char *name) {
    char service[256];
    int n = snprintf(service, sizeof(service), "%s.%s", SERVICE_PREFIX, name);
    if (n <= 0 || (size_t)n >= sizeof(service)) {
        return NULL;
    }

    UInt32 pw_len = 0;
    void  *pw_data = NULL;

    OSStatus st = SecKeychainFindGenericPassword(
        NULL,
        (UInt32)strlen(service), service,
        (UInt32)strlen(KC_ACCOUNT), KC_ACCOUNT,
        &pw_len, &pw_data,
        NULL);

    if (st != errSecSuccess) {
        fprintf(stderr,
            "cmdseal: keychain lookup failed for '%s' (OSStatus=%d).\n"
            "  This usually means either:\n"
            "    - the keychain entry was never created / was removed, or\n"
            "    - the ACL rejected this caller (tampered binary?).\n",
            service, (int)st);
        return NULL;
    }

    char *buf = (char *)malloc((size_t)pw_len + 1);
    if (!buf) {
        SecKeychainItemFreeContent(NULL, pw_data);
        return NULL;
    }
    memcpy(buf, pw_data, pw_len);
    buf[pw_len] = '\0';
    SecKeychainItemFreeContent(NULL, pw_data);
    return buf;
}

int main(int argc, char *argv[]) {
    (void)LABEL;

    /* Count tokens. */
    size_t ntok = 0;
    while (TOKENS[ntok] != NULL) ntok++;
    if (ntok == 0) die("empty command template (generator bug)", 2);

    /* Resolve every token into a concrete argv string. */
    char **out_argv = (char **)calloc(ntok + 1, sizeof(char *));
    if (!out_argv) die("out of memory", 2);

    for (size_t i = 0; i < ntok; i++) {
        const char *t = TOKENS[i];
        if (!t || !*t) {
            out_argv[i] = (char *)"";
            continue;
        }

        if ((unsigned char)t[0] == TOK_SECRET) {
            /* "\x01secret:NAME" -> skip "secret:" prefix */
            const char *name = t + 1;
            if (strncmp(name, "secret:", 7) == 0) name += 7;
            char *v = fetch_secret(name);
            if (!v) die("unable to resolve secret (see details above)", 3);
            out_argv[i] = v;
            continue;
        }

        if ((unsigned char)t[0] == TOK_ARG) {
            /* "\x02arg:N" -> skip "arg:" prefix */
            const char *p = t + 1;
            if (strncmp(p, "arg:", 4) == 0) p += 4;
            long idx = strtol(p, NULL, 10);
            if (idx < 1 || idx >= argc) {
                fprintf(stderr,
                    "cmdseal: missing positional arg %ld "
                    "(this binary requires at least %ld positional argument(s))\n",
                    idx, idx);
                exit(4);
            }
            out_argv[i] = argv[idx];
            continue;
        }

        /* Literal token — strdup so we can free uniformly if needed. */
        out_argv[i] = (char *)t;
    }

    out_argv[ntok] = NULL;

    /* Sanity: first token must be non-empty. */
    if (!out_argv[0] || !*out_argv[0]) die("empty program name", 2);

    /* Go. */
    execvp(out_argv[0], out_argv);

    /* execvp only returns on error. */
    fprintf(stderr, "cmdseal: execvp('%s') failed: %s\n",
            out_argv[0], strerror(errno));
    return 127;
}
