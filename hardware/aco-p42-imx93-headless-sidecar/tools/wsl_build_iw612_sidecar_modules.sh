#!/usr/bin/env bash
set -euo pipefail

readonly REPO_ROOT="/mnt/c/Users/Steven01152/Documents/ChatGPT/imx.93_lvef"
readonly SOURCE_DIR="/root/edgelvef-build/mwifiex-lf-6.6.36"
readonly KERNEL_OUT="/root/edgelvef-build/kernel-sidecar-out"
readonly TOOLCHAIN_BIN="/root/edgelvef-build/arm-gnu-toolchain-13.3.rel1-x86_64-aarch64-none-linux-gnu/bin"
readonly EXPECTED_COMMIT="e5c9a169d7b7a441a20d2cf10a9752e249b71cff"
readonly KERNEL_RELEASE="6.6.36-lts-next-gab2a7006a738-aco-sidecar"
readonly ARTIFACT_DIR="${REPO_ROOT}/artifacts/kernel/aco-sidecar"
readonly EVIDENCE_DIR="${REPO_ROOT}/docs/p42-imx93-sidecar/evidence/kernel-sidecar-build"
readonly STAGE_DIR="/root/edgelvef-build/iw612-sidecar-stage"
readonly ARCHIVE="${ARTIFACT_DIR}/iw612-modules-${KERNEL_RELEASE}.tar.gz"

if [[ ! -d "${SOURCE_DIR}/.git" && ! -f "${SOURCE_DIR}/.git" ]]; then
    echo "Missing pinned mwifiex worktree: ${SOURCE_DIR}" >&2
    exit 1
fi

actual_commit="$(git -C "${SOURCE_DIR}" rev-parse HEAD)"
if [[ "${actual_commit}" != "${EXPECTED_COMMIT}" ]]; then
    echo "Unexpected mwifiex commit: ${actual_commit}" >&2
    exit 1
fi

if [[ ! -f "${KERNEL_OUT}/include/generated/utsrelease.h" ]]; then
    echo "Missing prepared sidecar kernel output: ${KERNEL_OUT}" >&2
    exit 1
fi

actual_release="$(sed -n 's/^#define UTS_RELEASE "\(.*\)"/\1/p' "${KERNEL_OUT}/include/generated/utsrelease.h")"
if [[ "${actual_release}" != "${KERNEL_RELEASE}" ]]; then
    echo "Unexpected kernel release: ${actual_release}" >&2
    exit 1
fi

export PATH="${TOOLCHAIN_BIN}:${PATH}"
export ARCH=arm64
export CROSS_COMPILE="${TOOLCHAIN_BIN}/aarch64-none-linux-gnu-"

mkdir -p "${ARTIFACT_DIR}" "${EVIDENCE_DIR}"
rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}/lib/modules/${KERNEL_RELEASE}/updates"

started="$(date --iso-8601=seconds)"
cd "${SOURCE_DIR}"
make clean
make \
    KERNELDIR="${KERNEL_OUT}" \
    ARCH="${ARCH}" \
    CROSS_COMPILE="${CROSS_COMPILE}" \
    CC="${CROSS_COMPILE}gcc" \
    LD="${CROSS_COMPILE}ld" \
    CONFIG_64BIT=y \
    -j"$(nproc)"

install -m 0644 "${SOURCE_DIR}/mlan.ko" "${STAGE_DIR}/lib/modules/${KERNEL_RELEASE}/updates/mlan.ko"
install -m 0644 "${SOURCE_DIR}/moal.ko" "${STAGE_DIR}/lib/modules/${KERNEL_RELEASE}/updates/moal.ko"
tar -C "${STAGE_DIR}" -czf "${ARCHIVE}" "lib/modules/${KERNEL_RELEASE}/updates"
finished="$(date --iso-8601=seconds)"

{
    echo "source_repository=https://github.com/nxp-imx/mwifiex.git"
    echo "source_tag=lf-6.6.36-2.1.0"
    echo "source_commit=${actual_commit}"
    echo "kernel_release=${KERNEL_RELEASE}"
    echo "cross_compiler=$(${CROSS_COMPILE}gcc --version | head -n 1)"
    echo "build_started=${started}"
    echo "build_finished=${finished}"
    strings "${SOURCE_DIR}/mlan.ko" | grep '^vermagic='
    strings "${SOURCE_DIR}/moal.ko" | grep '^vermagic='
    sha256sum "${SOURCE_DIR}/mlan.ko" "${SOURCE_DIR}/moal.ko" "${ARCHIVE}"
} | tee "${EVIDENCE_DIR}/iw612-build-metadata.txt"

