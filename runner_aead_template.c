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
 *      embedded ciphertext, and execvp()s the resulting command.
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

#define TOK_ARG 0x02

static void die(const char *msg, int rc) {
    fprintf(stderr, "cmdseal: %s\n", msg);
    exit(rc);
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

int main(int argc, char *argv[]) {
    (void)LABEL;

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
     *    with an empty string. */
    size_t ntok = 0;
    {
        size_t i = 0;
        while (i < CIPHERTEXT_LEN && pt[i] != '\0') {
            size_t l = strlen((char *)(pt + i));
            ntok++;
            i += l + 1;
        }
    }
    if (ntok == 0) die("empty command (generator bug)", 2);

    char **out_argv = (char **)calloc(ntok + 1, sizeof(char *));
    if (!out_argv) die("out of memory", 2);

    {
        size_t i = 0, idx = 0;
        while (i < CIPHERTEXT_LEN && pt[i] != '\0') {
            char *t = (char *)(pt + i);
            size_t l = strlen(t);

            if ((unsigned char)t[0] == TOK_ARG) {
                /* "\x02arg:N" */
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
        out_argv[idx] = NULL;
    }

    if (!out_argv[0] || !*out_argv[0]) die("empty program name", 2);

    /* 4. Go. (pt stays allocated — out_argv points into it.) */
    execvp(out_argv[0], out_argv);

    fprintf(stderr, "cmdseal: execvp('%s') failed: %s\n",
            out_argv[0], strerror(errno));
    return 127;
}
