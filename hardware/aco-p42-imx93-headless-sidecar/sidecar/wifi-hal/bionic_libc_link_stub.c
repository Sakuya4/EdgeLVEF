/*
 * Link-time-only declarations used to add DT_NEEDED libc.so when building
 * outside a complete Android platform tree.  This file is never deployed;
 * Android's Bionic libc supplies the symbols at runtime.
 */

#include <stddef.h>
#include <sys/types.h>

int access(const char *path, int mode) { (void)path; (void)mode; return -1; }
int close(int fd) { (void)fd; return -1; }
void *memcpy(void *dst, const void *src, size_t n) {
    (void)src; (void)n; return dst;
}
int pipe(int fds[2]) { (void)fds; return -1; }
ssize_t read(int fd, void *buf, size_t n) {
    (void)fd; (void)buf; (void)n; return -1;
}
size_t strlen(const char *value) { (void)value; return 0; }
int usleep(unsigned int usec) { (void)usec; return -1; }
ssize_t write(int fd, const void *buf, size_t n) {
    (void)fd; (void)buf; (void)n; return -1;
}
