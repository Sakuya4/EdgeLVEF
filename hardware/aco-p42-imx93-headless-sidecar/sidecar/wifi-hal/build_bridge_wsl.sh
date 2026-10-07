#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
src="$repo_root/sidecar/wifi-hal/aco_wifi_hal_bridge.c"
libc_stub_src="$repo_root/sidecar/wifi-hal/bionic_libc_link_stub.c"
include_dir="$repo_root/vendor/aosp-libhardware-legacy-android12/include"
out_dir="$repo_root/artifacts/android-wifi-hal"

mkdir -p "$out_dir"

clang --target=aarch64-linux-gnu --gcc-toolchain=/usr \
  -O2 \
  -fPIC \
  -shared \
  -nostdlib \
  -fuse-ld=lld \
  -Wl,-soname,libc.so \
  -Wl,-z,max-page-size=4096 \
  -o "$out_dir/libc-link-stub.so" \
  "$libc_stub_src"

clang --target=aarch64-linux-gnu --gcc-toolchain=/usr \
  -std=gnu11 \
  -O2 \
  -fPIC \
  -fvisibility=hidden \
  -Wall \
  -Wextra \
  -Werror \
  -I"$include_dir" \
  -shared \
  -nostdlib \
  -fuse-ld=lld \
  -Wl,-z,max-page-size=4096 \
  -Wl,-soname,libwifi-hal-aco-bridge.so \
  -Wl,--build-id=sha1 \
  -Wl,--no-as-needed \
  -L"$out_dir" \
  -Wl,-l:libc-link-stub.so \
  -o "$out_dir/libwifi-hal-aco-bridge.so" \
  "$src"

rm -f "$out_dir/libc-link-stub.so"
sha256sum "$out_dir/libwifi-hal-aco-bridge.so" > "$out_dir/SHA256SUMS.txt"
readelf -Ws "$out_dir/libwifi-hal-aco-bridge.so" \
  | grep init_wifi_vendor_hal_func_table
