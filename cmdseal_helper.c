/*
 * cmdseal_helper — create a keychain generic-password with a
 *                  *strict* ACL that admits ONLY a single trusted
 *                  binary path.
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
 * Usage:
 *   cmdseal_helper add    <service> <account> <trusted_bin_path>
 *       (password is read from stdin; never passed via argv to avoid
 *        leakage through /proc-style process listings)
 *
 *   cmdseal_helper delete <service> <account>
 *       (probe-only: exercises SecKeychainItemDelete without ACL
 *        bump; used by modify_acl_probe.py to observe whether
 *        macOS prompts / times out / succeeds silently.)
 *
 *   cmdseal_helper update <service> <account>
 *       (probe-only: reads NEW password from stdin and calls
 *        SecKeychainItemModifyContent; same observational purpose.)
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
 *
 * Compile:
 *   cc -O2 -Wno-deprecated-declarations -o cmdseal_helper \
 *      cmdseal_helper.c -framework Security -framework CoreFoundation
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <Security/Security.h>
#include <CoreFoundation/CoreFoundation.h>

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

    /* Delete any pre-existing entry so we replace cleanly. */
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

usage:
    fprintf(stderr,
        "usage:\n"
        "  %s add    <service> <account> <trusted_bin_path>\n"
        "       (password on stdin)\n"
        "  %s delete <service> <account>\n"
        "  %s update <service> <account>\n"
        "       (new password on stdin)\n",
        argv[0], argv[0], argv[0]);
    return 64;
}
