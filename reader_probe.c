/*
 * reader_probe — imitates an "unauthorized caller" (e.g. the AI agent's
 * own process) trying to read the secret via the Security framework
 * directly. If our ACL works, this should either prompt or fail.
 */
#include <stdio.h>
#include <string.h>
#include <Security/Security.h>

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s <service> <account>\n", argv[0]);
        return 1;
    }
    UInt32 len = 0;
    void *data = NULL;
    OSStatus st = SecKeychainFindGenericPassword(
        NULL,
        (UInt32)strlen(argv[1]), argv[1],
        (UInt32)strlen(argv[2]), argv[2],
        &len, &data, NULL);
    if (st != errSecSuccess) {
        CFStringRef msg = SecCopyErrorMessageString(st, NULL);
        char buf[256] = {0};
        if (msg) {
            CFStringGetCString(msg, buf, sizeof(buf), kCFStringEncodingUTF8);
            CFRelease(msg);
        }
        fprintf(stderr, "probe: FAILED OSStatus=%d (%s)\n", (int)st, buf);
        return 2;
    }
    fwrite(data, 1, len, stdout);
    fputc('\n', stdout);
    SecKeychainItemFreeContent(NULL, data);
    return 0;
}
