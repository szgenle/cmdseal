/*
 * cmdseal_helper — create a keychain generic-password with a
 *                  *strict* ACL that admits ONLY a single trusted
 *                  binary path, plus a one-shot AES-256-GCM
 *                  encrypt subcommand for the Plan D generator.
 *
 * Why this exists:
 *   `security add-generic-password` always registers /usr/bin/security
 *   itself as a trusted app on the created entry's ACL. That lets any
 *   process in the user's session re-invoke /usr/bin/security to
 *   exfiltrate the secret silently — defeating the whole point of a
 *   capability-gated binary.
 *
 *   This helper uses the Security framework directly:
 *       SecAccessCreate(label, [trusted_bin])
 *       SecKeychainItemCreateFromContent(..., access, ...)
 *   which yields an ACL whose trusted-app list contains ONLY the
 *   caller-specified binary. Any other caller (including
 *   /usr/bin/security) is forced through the GUI confirmation prompt,
 *   which an unattended AI agent cannot click.
 *
 *   All keychain subcommands target the user's default keychain
 *   (login.keychain-db). Plan B (a dedicated custom keychain) was
 *   evaluated and abandoned; see NEXT.md §5.11 for the post-mortem.
 *
 * Usage:
 *   cmdseal_helper add    <service> <account> <trusted_bin_path>
 *       (password is read from stdin; never passed via argv to avoid
 *        leakage through /proc-style process listings)
 *
 *   cmdseal_helper delete <service> <account>
 *       (used by cmdseal rotate to destroy the old K after a
 *        successful re-seal. Also exercised by modify_acl_probe.py.)
 *
 *   cmdseal_helper update <service> <account>
 *       (probe-only: reads NEW password from stdin and calls
 *        SecKeychainItemModifyContent; used by modify_acl_probe.py.)
 *
 *   cmdseal_helper encrypt <key_hex>
 *       AES-256-GCM one-shot encrypt. Reads plaintext from stdin
 *       (binary-safe, no newline stripping). Generates a random
 *       12-byte nonce. Writes `nonce || ciphertext || tag` (tag =
 *       16 bytes) to stdout as raw binary.
 *       <key_hex> is 64 lowercase hex chars = 32 bytes AES-256 key.
 *
 * Exit codes:
 *   0   success
 *   64  bad usage
 *   65  SecTrustedApplicationCreateFromPath failed
 *   66  SecAccessCreate failed
 *   67  SecKeychainItemCreateFromContent failed
 *   68  stdin read failure / empty password
 *   69  SecKeychainFindGenericPassword failed (not found)
 *   70  SecKeychainItemDelete failed
 *   71  SecKeychainItemModifyContent failed
 *   72  bad key hex (wrong length or non-hex chars)
 *   73  CCCryptorGCMOneshotEncrypt failed
 *
 * Compile:
 *   cc -O2 -Wno-deprecated-declarations -o cmdseal_helper \
 *      cmdseal_helper.c -framework Security -framework CoreFoundation
 *   (CommonCrypto is part of libSystem; no extra -framework needed.)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <Security/Security.h>
#include <CoreFoundation/CoreFoundation.h>
#include <CommonCrypto/CommonCryptor.h>

/* AES-GCM one-shot APIs: exported from libSystem (CommonCrypto SPI),
 * stable since macOS 10.13 / iOS 11, but not declared in the public
 * SDK's <CommonCrypto/CommonCryptor.h>. Forward-declare here. */
extern CCCryptorStatus CCCryptorGCMOneshotEncrypt(
    CCAlgorithm alg,
    const void *key, size_t keyLength,
    const void *iv, size_t ivLength,
    const void *aData, size_t aDataLength,
    const void *dataIn, size_t dataInLength,
    void *dataOut,
    void *tagOut, size_t tagLength);
extern CCCryptorStatus CCCryptorGCMOneshotDecrypt(
    CCAlgorithm alg,
    const void *key, size_t keyLength,
    const void *iv, size_t ivLength,
    const void *aData, size_t aDataLength,
    const void *dataIn, size_t dataInLength,
    void *dataOut,
    const void *tagIn, size_t tagLength);

static void report(const char *op, OSStatus st) {
    CFStringRef msg = SecCopyErrorMessageString(st, NULL);
    char buf[256] = {0};
    if (msg) {
        CFStringGetCString(msg, buf, sizeof(buf), kCFStringEncodingUTF8);
        CFRelease(msg);
    }
    fprintf(stderr, "cmdseal_helper: %s failed: %d (%s)\n",
            op, (int)st, buf[0] ? buf : "?");
}

static int cmd_add(const char *svc, const char *acct,
                   const char *pw,  const char *trusted_path) {
    OSStatus st;

    /* Delete any pre-existing entry in the default keychain so we
     * replace cleanly. */
    SecKeychainItemRef old = NULL;
    st = SecKeychainFindGenericPassword(
        NULL,
        (UInt32)strlen(svc),  svc,
        (UInt32)strlen(acct), acct,
        NULL, NULL, &old);
    if (st == errSecSuccess && old) {
        SecKeychainItemDelete(old);
        CFRelease(old);
    }

    /* Build the single-app trusted list. */
    SecTrustedApplicationRef app = NULL;
    st = SecTrustedApplicationCreateFromPath(trusted_path, &app);
    if (st != errSecSuccess) {
        report("SecTrustedApplicationCreateFromPath", st);
        return 65;
    }
    const void *appArr[] = { app };
    CFArrayRef trustedArray = CFArrayCreate(
        NULL, appArr, 1, &kCFTypeArrayCallBacks);

    CFStringRef label = CFStringCreateWithCString(
        NULL, svc, kCFStringEncodingUTF8);

    SecAccessRef access = NULL;
    st = SecAccessCreate(label, trustedArray, &access);
    CFRelease(label);
    CFRelease(trustedArray);
    CFRelease(app);
    if (st != errSecSuccess) {
        report("SecAccessCreate", st);
        return 66;
    }

    /* Create the generic-password item with our strict ACL. */
    SecKeychainAttribute attrs[] = {
        { kSecServiceItemAttr, (UInt32)strlen(svc),  (char *)svc  },
        { kSecAccountItemAttr, (UInt32)strlen(acct), (char *)acct },
    };
    SecKeychainAttributeList attrList = { 2, attrs };

    SecKeychainItemRef item = NULL;
    st = SecKeychainItemCreateFromContent(
        kSecGenericPasswordItemClass,
        &attrList,
        (UInt32)strlen(pw), pw,
        NULL,           /* default keychain (login) */
        access,
        &item);

    CFRelease(access);
    if (st != errSecSuccess) {
        report("SecKeychainItemCreateFromContent", st);
        return 67;
    }
    if (item) CFRelease(item);
    return 0;
}

static int cmd_delete(const char *svc, const char *acct) {
    SecKeychainItemRef item = NULL;
    OSStatus st = SecKeychainFindGenericPassword(
        NULL,
        (UInt32)strlen(svc),  svc,
        (UInt32)strlen(acct), acct,
        NULL, NULL, &item);
    if (st != errSecSuccess || !item) {
        report("SecKeychainFindGenericPassword", st);
        return 69;
    }
    st = SecKeychainItemDelete(item);
    CFRelease(item);
    if (st != errSecSuccess) {
        report("SecKeychainItemDelete", st);
        return 70;
    }
    return 0;
}

static int cmd_update(const char *svc, const char *acct, const char *pw) {
    SecKeychainItemRef item = NULL;
    OSStatus st = SecKeychainFindGenericPassword(
        NULL,
        (UInt32)strlen(svc),  svc,
        (UInt32)strlen(acct), acct,
        NULL, NULL, &item);
    if (st != errSecSuccess || !item) {
        report("SecKeychainFindGenericPassword", st);
        return 69;
    }
    st = SecKeychainItemModifyContent(
        item, NULL, (UInt32)strlen(pw), pw);
    CFRelease(item);
    if (st != errSecSuccess) {
        report("SecKeychainItemModifyContent", st);
        return 71;
    }
    return 0;
}

/* Read the entire stdin into a heap buffer (caller frees). Strips a
 * single trailing newline. Returns 0 on success, 68 on failure.
 * On success, *out_buf / *out_len are set. */
static int read_password_stdin(char **out_buf, size_t *out_len) {
    size_t cap = 256, len = 0;
    char *buf = (char *)malloc(cap);
    if (!buf) return 68;
    int c;
    while ((c = fgetc(stdin)) != EOF) {
        if (len + 1 >= cap) {
            cap *= 2;
            char *nb = (char *)realloc(buf, cap);
            if (!nb) { free(buf); return 68; }
            buf = nb;
        }
        buf[len++] = (char)c;
    }
    if (len > 0 && buf[len - 1] == '\n') len--;
    if (len == 0) {
        fprintf(stderr, "cmdseal_helper: empty password on stdin\n");
        free(buf);
        return 68;
    }
    buf[len] = '\0';
    *out_buf = buf;
    *out_len = len;
    return 0;
}

/* Binary-safe stdin read (no newline stripping, no non-empty check).
 * Used for `encrypt` which must pass plaintext through verbatim,
 * including embedded NULs. */
static int read_stdin_binary(unsigned char **out_buf, size_t *out_len) {
    size_t cap = 256, len = 0;
    unsigned char *buf = (unsigned char *)malloc(cap);
    if (!buf) return 68;
    int c;
    while ((c = fgetc(stdin)) != EOF) {
        if (len >= cap) {
            cap *= 2;
            unsigned char *nb = (unsigned char *)realloc(buf, cap);
            if (!nb) { free(buf); return 68; }
            buf = nb;
        }
        buf[len++] = (unsigned char)c;
    }
    *out_buf = buf;
    *out_len = len;
    return 0;
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

static int cmd_encrypt(const char *keyhex) {
    /* 1. Decode key. */
    size_t hl = strlen(keyhex);
    if (hl != 64) {
        fprintf(stderr,
            "cmdseal_helper: key_hex must be 64 chars (got %zu)\n", hl);
        return 72;
    }
    unsigned char key[32];
    if (hex_decode(keyhex, 64, key, 32) != 0) {
        fprintf(stderr, "cmdseal_helper: key_hex is not valid hex\n");
        return 72;
    }

    /* 2. Read plaintext (binary-safe). */
    unsigned char *pt = NULL;
    size_t ptlen = 0;
    int r = read_stdin_binary(&pt, &ptlen);
    if (r != 0) { memset(key, 0, 32); return r; }

    /* 3. Random nonce. */
    unsigned char nonce[12];
    arc4random_buf(nonce, 12);

    /* 4. Encrypt. */
    unsigned char *ct = (unsigned char *)malloc(ptlen ? ptlen : 1);
    if (!ct) { memset(key, 0, 32); free(pt); return 68; }
    unsigned char tag[16];

    CCCryptorStatus cst = CCCryptorGCMOneshotEncrypt(
        kCCAlgorithmAES,
        key, 32,
        nonce, 12,
        NULL, 0,            /* no AAD */
        pt, ptlen,
        ct,
        tag, 16);

    memset(key, 0, 32);
    memset(pt, 0, ptlen);
    free(pt);

    if (cst != kCCSuccess) {
        fprintf(stderr,
            "cmdseal_helper: CCCryptorGCMOneshotEncrypt failed (%d)\n",
            (int)cst);
        free(ct);
        return 73;
    }

    /* 5. Emit nonce || ct || tag on stdout. */
    if (fwrite(nonce, 1, 12, stdout) != 12 ||
        (ptlen > 0 && fwrite(ct, 1, ptlen, stdout) != ptlen) ||
        fwrite(tag, 1, 16, stdout) != 16) {
        free(ct);
        return 68;
    }
    fflush(stdout);
    free(ct);
    return 0;
}

int main(int argc, char *argv[]) {
    if (argc < 2) goto usage;

    if (strcmp(argv[1], "add") == 0) {
        if (argc != 5) goto usage;

        char *buf = NULL;
        size_t len = 0;
        int r = read_password_stdin(&buf, &len);
        if (r != 0) return r;
        int rc = cmd_add(argv[2], argv[3], buf, argv[4]);
        /* Best-effort scrub. */
        memset(buf, 0, len);
        free(buf);
        return rc;
    }

    if (strcmp(argv[1], "delete") == 0) {
        if (argc != 4) goto usage;
        return cmd_delete(argv[2], argv[3]);
    }

    if (strcmp(argv[1], "update") == 0) {
        if (argc != 4) goto usage;
        char *buf = NULL;
        size_t len = 0;
        int r = read_password_stdin(&buf, &len);
        if (r != 0) return r;
        int rc = cmd_update(argv[2], argv[3], buf);
        memset(buf, 0, len);
        free(buf);
        return rc;
    }

    if (strcmp(argv[1], "encrypt") == 0) {
        if (argc != 3) goto usage;
        return cmd_encrypt(argv[2]);
    }

usage:
    fprintf(stderr,
        "usage:\n"
        "  %s add    <service> <account> <trusted_bin_path>\n"
        "       (password on stdin)\n"
        "  %s delete <service> <account>\n"
        "  %s update <service> <account>\n"
        "       (new password on stdin)\n"
        "  %s encrypt <key_hex>\n"
        "       (plaintext on stdin; emits nonce||ct||tag on stdout)\n",
        argv[0], argv[0], argv[0], argv[0]);
    return 64;
}
