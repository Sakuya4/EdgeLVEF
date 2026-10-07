#!/usr/bin/env bash
set -euo pipefail

readonly source_dir="${SOURCE_DIR:-/root/edgelvef-build/linux-imx}"
readonly build_dir="${BUILD_DIR:-/root/edgelvef-build/kernel-sidecar-out}"
readonly module_stage="${MODULE_STAGE:-/root/edgelvef-build/modules-sidecar-stage}"
readonly workspace="${WORKSPACE:-/mnt/c/Users/Steven01152/Documents/ChatGPT/imx.93_lvef}"
readonly baseline_config_gz="${BASELINE_CONFIG_GZ:-${workspace}/docs/p42-imx93-sidecar/evidence/board/config-6.6.36-lts-next-gab2a7006a738.gz}"
readonly artifact_dir="${ARTIFACT_DIR:-${workspace}/artifacts/kernel/aco-sidecar}"
readonly evidence_dir="${EVIDENCE_DIR:-${workspace}/docs/p42-imx93-sidecar/evidence/kernel-sidecar-build}"
readonly expected_source_commit="d23d64eea5111e1607efcce1d601834fceec92cb"
readonly localversion="-aco-sidecar"
readonly expected_kernel_release="6.6.36-lts-next-gab2a7006a738${localversion}"
readonly cross_compile="${CROSS_COMPILE:-/root/edgelvef-build/arm-gnu-toolchain-13.3.rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-}"
readonly jobs="${JOBS:-6}"

test -d "${source_dir}/.git"
test -r "${baseline_config_gz}"

actual_source_commit="$(git -C "${source_dir}" rev-parse HEAD)"
if [[ "${actual_source_commit}" != "${expected_source_commit}" ]]; then
    echo "Unexpected kernel source commit: ${actual_source_commit}" >&2
    exit 1
fi

mkdir -p "${build_dir}" "${artifact_dir}" "${evidence_dir}"
gzip -dc "${baseline_config_gz}" > "${evidence_dir}/board-running.config"
cp "${evidence_dir}/board-running.config" "${build_dir}/.config"

"${source_dir}/scripts/config" --file "${build_dir}/.config" \
    --enable ANDROID_BINDER_IPC \
    --enable ANDROID_BINDERFS \
    --set-str ANDROID_BINDER_DEVICES "binder,hwbinder,vndbinder" \
    --enable PSI \
    --disable PSI_DEFAULT_DISABLED

make -C "${source_dir}" O="${build_dir}" \
    ARCH=arm64 CROSS_COMPILE="${cross_compile}" LOCALVERSION="${localversion}" olddefconfig

kernel_release="$(make -s -C "${source_dir}" O="${build_dir}" \
    ARCH=arm64 CROSS_COMPILE="${cross_compile}" LOCALVERSION="${localversion}" kernelrelease)"
if [[ "${kernel_release}" != "${expected_kernel_release}" ]]; then
    echo "Unexpected kernel release: ${kernel_release}" >&2
    exit 1
fi

grep -qx 'CONFIG_ANDROID_BINDER_IPC=y' "${build_dir}/.config"
grep -qx 'CONFIG_ANDROID_BINDERFS=y' "${build_dir}/.config"
grep -qx 'CONFIG_ANDROID_BINDER_DEVICES="binder,hwbinder,vndbinder"' "${build_dir}/.config"
grep -qx 'CONFIG_PSI=y' "${build_dir}/.config"
grep -qx '# CONFIG_PSI_DEFAULT_DISABLED is not set' "${build_dir}/.config"

diff -u "${evidence_dir}/board-running.config" "${build_dir}/.config" \
    > "${evidence_dir}/sidecar-config.diff" || true

unexpected_changes="$({
    grep -E '^[+-](CONFIG_|# CONFIG_)' "${evidence_dir}/sidecar-config.diff" || true
} | sed -E 's/^[+-](# )?([^= ]+).*/\2/' | sort -u \
  | grep -Ev '^CONFIG_(ANDROID_BINDER_IPC|ANDROID_BINDERFS|ANDROID_BINDER_DEVICES|ANDROID_BINDER_IPC_SELFTEST|PSI|PSI_DEFAULT_DISABLED|CC_VERSION_TEXT|GCC_VERSION|CC_CAN_LINK_STATIC|PAHOLE_VERSION|PAHOLE_HAS_SPLIT_BTF|PAHOLE_HAS_LANG_EXCLUDE|DEBUG_INFO_COMPRESSED_ZSTD|GCC_PLUGINS|DRM_PANEL_WAVESHARE_DSI)$' || true)"
if [[ -n "${unexpected_changes}" ]]; then
    echo "Unexpected configuration changes:" >&2
    echo "${unexpected_changes}" >&2
    exit 1
fi

{
    echo "source_commit=${actual_source_commit}"
    echo "source_tag=$(git -C "${source_dir}" describe --tags --exact-match)"
    echo "kernel_release=${kernel_release}"
    echo "cross_compiler=$(${cross_compile}gcc --version | head -n 1)"
    echo "jobs=${jobs}"
    echo "build_started=$(date --iso-8601=seconds)"
} > "${evidence_dir}/build-metadata.txt"

make -C "${source_dir}" O="${build_dir}" \
    ARCH=arm64 CROSS_COMPILE="${cross_compile}" LOCALVERSION="${localversion}" \
    -j"${jobs}" Image modules \
    2>&1 | tee "${evidence_dir}/build.log"

install -m 0644 "${build_dir}/arch/arm64/boot/Image" \
    "${artifact_dir}/Image.aco-sidecar"
install -m 0644 "${build_dir}/.config" \
    "${artifact_dir}/config.aco-sidecar"
install -m 0644 "${build_dir}/System.map" \
    "${artifact_dir}/System.map.aco-sidecar"

case "${module_stage}" in
    /root/edgelvef-build/*) ;;
    *) echo "Unsafe module staging path: ${module_stage}" >&2; exit 1 ;;
esac
rm -rf -- "${module_stage}"
make -C "${source_dir}" O="${build_dir}" \
    ARCH=arm64 CROSS_COMPILE="${cross_compile}" LOCALVERSION="${localversion}" \
    modules_install INSTALL_MOD_PATH="${module_stage}" INSTALL_MOD_STRIP=1
test -d "${module_stage}/lib/modules/${kernel_release}"
tar -C "${module_stage}" -czf \
    "${artifact_dir}/modules-${kernel_release}.tar.gz" \
    "lib/modules/${kernel_release}"

{
    cat "${evidence_dir}/build-metadata.txt"
    echo "build_finished=$(date --iso-8601=seconds)"
    sha256sum \
        "${artifact_dir}/Image.aco-sidecar" \
        "${artifact_dir}/config.aco-sidecar" \
        "${artifact_dir}/System.map.aco-sidecar" \
        "${artifact_dir}/modules-${kernel_release}.tar.gz"
} > "${artifact_dir}/SHA256SUMS.txt"

file "${artifact_dir}/Image.aco-sidecar"
cat "${artifact_dir}/SHA256SUMS.txt"
