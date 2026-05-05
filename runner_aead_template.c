/*
 * cmdseal Plan D runner template (AEAD-sealed command)
 *
 * This file is a TEMPLATE. cmdseal.py locates the @@NAME@@ block-
 * comment markers and substitutes in project-specific values, then
 * compiles the result into a capability-gated executable.
 *
 * Design (Plan D; see NEXT.md §5):
 *   1. Generator picks a random 32-byte AES-256 key K (stored as
 *      64-char lowercase hex in the user's login keychain, under a
 *      strict ACL that only admits THIS signed binary).
 *   2. Generator serializes the command tokens into a plaintext blob
 *      (double-NUL-terminated C strings), AES-256-GCM encrypts it
 *      with K and a random 12-byte nonce, and hardcodes the
 *      resulting nonce || ciphertext || tag into this file.
 *   3. At runtime, this binary fetches K from keychain, decrypts the
 *      embedded ciphertext, and execv()s the resulting command.
 *      v1.1 hardening: env DYLD_* and LD_* are stripped before
 *      execv (#3), and the first token MUST be an absolute path
 *      — no PATH lookup happens at runtime (#2).
 *      If decryption fails (auth tag mismatch), it aborts — so an
 *      attacker who silently swaps the keychain value for a known K'
 *      cannot redirect execution.
 *
 * Tokens are one of:
 *   "literal"          -> used verbatim
 *   "\x02arg:N"        -> replaced by argv[N] of this binary (1-based)
 * (Plan D removes the old "\x01secret:NAME" token type; the whole
 *  command is the secret now.)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <crt_externs.h>   /* _NSGetEnviron on macOS */
#include <Security/Security.h>
#include <CommonCrypto/CommonCryptor.h>

/* AES-GCM one-shot APIs: exported from libSystem (CommonCrypto SPI),
 * stable since macOS 10.13 but not in the public SDK header. */
extern CCCryptorStatus CCCryptorGCMOneshotDecrypt(
    CCAlgorithm alg,
    const void *key, size_t keyLength,
    const void *iv, size_t ivLength,
    const void *aData, size_t aDataLength,
    const void *dataIn, size_t dataInLength,
    void *dataOut,
    const void *tagIn, size_t tagLength);

/* ============================================================
 * BEGIN generator-filled section
 * ============================================================ */

/* Full keychain service name. The item stores K as 64 hex chars. */
static const char *KC_SERVICE = /* @@KC_SERVICE@@ */ "cmdseal.example.K";

/* Keychain account = current user's login name at generation time. */
static const char *KC_ACCOUNT = /* @@KC_ACCOUNT@@ */ "unknown";

/* Human-readable label (shown on keychain prompts if ACL is violated). */
static const char *LABEL = /* @@LABEL@@ */ "cmdseal sealed command";

/* AEAD nonce (12 bytes). */
static const unsigned char NONCE[] = /* @@NONCE@@ */ {
    0
};

/* AEAD ciphertext (same length as the serialized plaintext). */
static const unsigned char CIPHERTEXT[] = /* @@CIPHERTEXT@@ */ {
    0
};
static const size_t CIPHERTEXT_LEN = /* @@CIPHERTEXT_LEN@@ */ 0;

/* AEAD authentication tag (16 bytes). */
static const unsigned char TAG[] = /* @@TAG@@ */ {
    0
};

/* ============================================================
 * END generator-filled section
 * ============================================================ */

#define TOK_ARG  0x02
#define TOK_PIPE 0x03

/* v1.2: hard cap on pipeline depth. Must match MAX_PIPE_SEGMENTS
 * in cmdseal.py. See research/DESIGN.pipe.md §2.4. */
#define MAX_PIPE_SEGMENTS 8

static void die(const char *msg, int rc) {
    fprintf(stderr, "cmdseal: %s\n", msg);
    exit(rc);
}

/* v1.1 #3: strip DYLD_* and LD_* from our environment BEFORE
 * decrypting or exec'ing. The hardened runtime (v1.1 #4) makes dyld
 * ignore these for THIS binary; this unsetenv makes sure the child
 * process we execv() does not inherit a caller's injection attempt
 * either. Defence in depth — does nothing when the caller was
 * already honest, costs ~microseconds otherwise. */
static void strip_dangerous_env(void) {
    char ***envp = _NSGetEnviron();
    if (!envp || !*envp) return;
    /* First pass: collect keys. Do not unsetenv() while iterating
     * because it mutates the environ array. */
    size_t cap = 16, n = 0;
    char **keys = (char **)malloc(cap * sizeof(char *));
    if (!keys) return;
    for (char **e = *envp; *e; e++) {
        const char *eq = strchr(*e, '=');
        if (!eq) continue;
        size_t klen = (size_t)(eq - *e);
        int dangerous =
            (klen >= 5 && strncmp(*e, "DYLD_", 5) == 0) ||
            (klen >= 3 && strncmp(*e, "LD_",   3) == 0);
        if (!dangerous) continue;
        if (n == cap) {
            cap *= 2;
            char **nk = (char **)realloc(keys, cap * sizeof(char *));
            if (!nk) { free(keys); return; }
            keys = nk;
        }
        char *k = (char *)malloc(klen + 1);
        if (!k) continue;
        memcpy(k, *e, klen);
        k[klen] = '\0';
        keys[n++] = k;
    }
    for (size_t i = 0; i < n; i++) {
        unsetenv(keys[i]);
        free(keys[i]);
    }
    free(keys);
}

static int hex_decode(const char *hex, size_t hexlen,
                      unsigned char *out, size_t outcap) {
    if (hexlen != outcap * 2) return -1;
    for (size_t i = 0; i < outcap; i++) {
        int hi, lo;
        char h = hex[2*i], l = hex[2*i + 1];
        if      (h >= '0' && h <= '9') hi = h - '0';
        else if (h >= 'a' && h <= 'f') hi = 10 + (h - 'a');
        else if (h >= 'A' && h <= 'F') hi = 10 + (h - 'A');
        else return -1;
        if      (l >= '0' && l <= '9') lo = l - '0';
        else if (l >= 'a' && l <= 'f') lo = 10 + (l - 'a');
        else if (l >= 'A' && l <= 'F') lo = 10 + (l - 'A');
        else return -1;
        out[i] = (unsigned char)((hi << 4) | lo);
    }
    return 0;
}

/* Fetch K (as hex string) from the default keychain (login). Returns
 * malloc'd buffer of length pw_len (NOT necessarily 64 if corrupted),
 * with a trailing NUL at [pw_len]. Caller must free. Returns NULL
 * on failure. */
static char *fetch_key_hex(UInt32 *out_len) {
    UInt32 pw_len = 0;
    void  *pw_data = NULL;

    OSStatus st = SecKeychainFindGenericPassword(
        NULL,       /* default keychain (login) */
        (UInt32)strlen(KC_SERVICE), KC_SERVICE,
        (UInt32)strlen(KC_ACCOUNT), KC_ACCOUNT,
        &pw_len, &pw_data,
        NULL);

    if (st != errSecSuccess) {
        fprintf(stderr,
            "cmdseal: keychain lookup failed for '%s' (OSStatus=%d).\n"
            "  Likely causes:\n"
            "    - the keychain item was deleted or never created\n"
            "      (rerun cmdseal to regenerate), or\n"
            "    - the ACL rejected this caller (tampered binary?).\n"
            "  Label: %s\n",
            KC_SERVICE, (int)st, LABEL);
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
    *out_len = pw_len;
    return buf;
}

/* v1.2: run a pipeline of `nsegs` segments. Each segment is a
 * NULL-terminated argv slice. stdout of segment i is wired to stdin
 * of segment i+1 via pipe(); stderr is inherited from the sealed
 * binary (matches shell default).
 *
 * Exit-code policy: first-failure-wins (pipefail-equivalent).
 * If any segment exits non-zero, the sealed binary exits with the
 * LEFTMOST failing code; all segments still run to completion.
 *
 * See research/DESIGN.pipe.md §2.3 and §4.
 */
static int run_pipeline(char **seg_argv[], size_t nsegs) {
    pid_t pids[MAX_PIPE_SEGMENTS];
    int prev_read = -1;

    for (size_t i = 0; i < nsegs; i++) {
        int pipefd[2] = {-1, -1};
        int has_next = (i + 1 < nsegs);

        if (has_next) {
            if (pipe(pipefd) != 0) {
                fprintf(stderr, "cmdseal: pipe() failed: %s\n",
                        strerror(errno));
                if (prev_read != -1) close(prev_read);
                return 2;
            }
        }

        pid_t pid = fork();
        if (pid < 0) {
            fprintf(stderr, "cmdseal: fork() failed: %s\n",
                    strerror(errno));
            if (prev_read != -1) close(prev_read);
            if (has_next) { close(pipefd[0]); close(pipefd[1]); }
            return 2;
        }

        if (pid == 0) {
            /* child */
            /* Restore SIGPIPE to default so that a downstream stage
             * closing its stdin (e.g. `head`) kills the upstream
             * producer — same behaviour as a shell pipeline. */
            signal(SIGPIPE, SIG_DFL);

            if (prev_read != -1) {
                if (dup2(prev_read, STDIN_FILENO) < 0) _exit(2);
                close(prev_read);
            }
            if (has_next) {
                close(pipefd[0]);
                if (dup2(pipefd[1], STDOUT_FILENO) < 0) _exit(2);
                close(pipefd[1]);
            }

            execv(seg_argv[i][0], seg_argv[i]);
            fprintf(stderr, "cmdseal: execv('%s') failed: %s\n",
                    seg_argv[i][0], strerror(errno));
            _exit(127);
        }

        /* parent */
        pids[i] = pid;
        if (prev_read != -1) close(prev_read);
        if (has_next) {
            close(pipefd[1]);
            prev_read = pipefd[0];
        } else {
            prev_read = -1;
        }
    }

    /* Wait all; first-failure-wins. */
    int first_fail = 0;
    for (size_t i = 0; i < nsegs; i++) {
        int st = 0;
        if (waitpid(pids[i], &st, 0) < 0) {
            if (first_fail == 0) first_fail = 2;
            continue;
        }
        int code = WIFEXITED(st) ? WEXITSTATUS(st)
                 : WIFSIGNALED(st) ? (128 + WTERMSIG(st))
                 : 1;
        if (code != 0 && first_fail == 0) first_fail = code;
    }
    return first_fail;
}

int main(int argc, char *argv[]) {
    (void)LABEL;

    /* v1.1 #3: drop dylib-injection vectors from env before anything. */
    strip_dangerous_env();

    /* 1. Fetch K from keychain. */
    UInt32 keyhex_len = 0;
    char *keyhex = fetch_key_hex(&keyhex_len);
    if (!keyhex) die("unable to resolve key (see details above)", 3);

    if (keyhex_len != 64) {
        memset(keyhex, 0, keyhex_len);
        free(keyhex);
        die("key in keychain has wrong length (corrupted? rerun cmdseal)", 3);
    }

    unsigned char K[32];
    if (hex_decode(keyhex, 64, K, 32) != 0) {
        memset(keyhex, 0, 64);
        free(keyhex);
        die("key in keychain is not valid hex (corrupted?)", 3);
    }
    memset(keyhex, 0, 64);
    free(keyhex);

    /* 2. Decrypt embedded ciphertext. */
    unsigned char *pt = (unsigned char *)malloc(
        CIPHERTEXT_LEN > 0 ? CIPHERTEXT_LEN + 1 : 2);
    if (!pt) { memset(K, 0, 32); die("out of memory", 2); }

    CCCryptorStatus cst = CCCryptorGCMOneshotDecrypt(
        kCCAlgorithmAES,
        K, 32,
        NONCE, sizeof(NONCE),
        NULL, 0,                        /* no AAD */
        CIPHERTEXT, CIPHERTEXT_LEN,
        pt,
        TAG, sizeof(TAG));

    memset(K, 0, 32);

    if (cst != kCCSuccess) {
        free(pt);
        die("ciphertext authentication failed — binary or keychain "
            "item was tampered with (ABORT)", 5);
    }
    pt[CIPHERTEXT_LEN] = '\0';

    /* 3. Parse tokens: sequence of NUL-terminated C strings, ending
     *    with an empty string. v1.2 introduces the one-byte TOK_PIPE
     *    separator (\x03) between pipeline segments. When no TOK_PIPE
     *    is present the layout is byte-identical to v1.1 and the code
     *    below collapses to the single-segment fast path. */
    size_t total_slots = 0;   /* non-pipe tokens */
    size_t nsegs       = 1;   /* at least one segment */
    {
        size_t i = 0;
        while (i < CIPHERTEXT_LEN && pt[i] != '\0') {
            size_t l = strlen((char *)(pt + i));
            if (l == 1 && (unsigned char)pt[i] == TOK_PIPE) {
                nsegs++;
                if (nsegs > MAX_PIPE_SEGMENTS) {
                    die("too many pipe segments (generator bug?)", 2);
                }
            } else {
                total_slots++;
            }
            i += l + 1;
        }
    }
    if (total_slots == 0) die("empty command (generator bug)", 2);

    /* Allocate one flat argv with room for: every real token, plus
     * one NULL terminator per segment. seg_argv[s] points into this
     * flat buffer at the start of segment s. */
    char **out_argv = (char **)calloc(total_slots + nsegs, sizeof(char *));
    if (!out_argv) die("out of memory", 2);

    char **seg_argv[MAX_PIPE_SEGMENTS];
    size_t seg_count = 0;
    seg_argv[0] = out_argv;

    {
        size_t i = 0, idx = 0;
        while (i < CIPHERTEXT_LEN && pt[i] != '\0') {
            char *t = (char *)(pt + i);
            size_t l = strlen(t);

            if (l == 1 && (unsigned char)t[0] == TOK_PIPE) {
                /* Close current segment and start the next one. */
                out_argv[idx++] = NULL;
                seg_count++;
                seg_argv[seg_count] = &out_argv[idx];
            } else if ((unsigned char)t[0] == TOK_ARG) {
                /* "\x02arg:N" — substitute argv[N] of this binary. */
                const char *p = t + 1;
                if (strncmp(p, "arg:", 4) == 0) p += 4;
                long argidx = strtol(p, NULL, 10);
                if (argidx < 1 || argidx >= argc) {
                    fprintf(stderr,
                        "cmdseal: missing positional arg %ld "
                        "(this binary requires at least %ld "
                        "positional argument(s))\n",
                        argidx, argidx);
                    exit(4);
                }
                out_argv[idx++] = argv[argidx];
            } else {
                out_argv[idx++] = t;
            }
            i += l + 1;
        }
        out_argv[idx] = NULL;   /* final terminator for last segment */
        seg_count++;
    }

    /* v1.1 #2 carried through to every segment: refuse PATH-based
     * lookup. First token of EACH segment must be an absolute path.
     * Checked in parent before any fork so the whole pipeline fails
     * cleanly without partial side-effects. */
    for (size_t s = 0; s < seg_count; s++) {
        if (!seg_argv[s][0] || !*seg_argv[s][0]) {
            die("empty program name in pipeline segment", 2);
        }
        if (seg_argv[s][0][0] != '/') {
            fprintf(stderr,
                "cmdseal: sealed command's program is not an absolute "
                "path (segment %zu: '%s'). Rerun cmdseal seal with a "
                "v1.1+ generator so the absolute path is baked in.\n",
                s + 1, seg_argv[s][0]);
            return 126;
        }
    }

    /* 4. Go. (pt stays allocated — out_argv points into it.) */
    if (seg_count == 1) {
        /* Fast path: single segment, no fork — identical to v1.1. */
        execv(seg_argv[0][0], seg_argv[0]);
        fprintf(stderr, "cmdseal: execv('%s') failed: %s\n",
                seg_argv[0][0], strerror(errno));
        return 127;
    }

    /* Slow path: stdout→stdin pipeline across seg_count stages. */
    return run_pipeline(seg_argv, seg_count);
}
