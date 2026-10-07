#!/usr/bin/env python3
"""Create the pinned, headless Android 12 OCI configuration for i.MX93."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ALL_CAPABILITIES = [
    "CAP_AUDIT_CONTROL",
    "CAP_AUDIT_READ",
    "CAP_AUDIT_WRITE",
    "CAP_BLOCK_SUSPEND",
    "CAP_BPF",
    "CAP_CHECKPOINT_RESTORE",
    "CAP_CHOWN",
    "CAP_DAC_OVERRIDE",
    "CAP_DAC_READ_SEARCH",
    "CAP_FOWNER",
    "CAP_FSETID",
    "CAP_IPC_LOCK",
    "CAP_IPC_OWNER",
    "CAP_KILL",
    "CAP_LEASE",
    "CAP_LINUX_IMMUTABLE",
    "CAP_MAC_ADMIN",
    "CAP_MAC_OVERRIDE",
    "CAP_MKNOD",
    "CAP_NET_ADMIN",
    "CAP_NET_BIND_SERVICE",
    "CAP_NET_BROADCAST",
    "CAP_NET_RAW",
    "CAP_PERFMON",
    "CAP_SETFCAP",
    "CAP_SETGID",
    "CAP_SETPCAP",
    "CAP_SETUID",
    "CAP_SYS_ADMIN",
    "CAP_SYS_BOOT",
    "CAP_SYS_CHROOT",
    "CAP_SYS_MODULE",
    "CAP_SYS_NICE",
    "CAP_SYS_PACCT",
    "CAP_SYS_PTRACE",
    "CAP_SYS_RAWIO",
    "CAP_SYS_RESOURCE",
    "CAP_SYS_TIME",
    "CAP_SYS_TTY_CONFIG",
    "CAP_SYSLOG",
    "CAP_WAKE_ALARM",
]


def device(path: str, major: int, minor: int, mode: int = 0o666) -> dict:
    return {
        "path": path,
        "type": "c",
        "major": major,
        "minor": minor,
        "fileMode": mode,
        "uid": 0,
        "gid": 0,
    }


def bind_mount(source: str, destination: str) -> dict:
    return {
        "destination": destination,
        "type": "none",
        "source": source,
        "options": ["rbind", "rw"],
    }


def make_config(
    rootfs: str,
    data_dir: str,
    memory_bytes: int,
    share_host_network: bool = False,
) -> dict:
    capabilities = {
        name: list(ALL_CAPABILITIES)
        for name in ("bounding", "effective", "inheritable", "permitted", "ambient")
    }
    mounts = [
        {"destination": "/proc", "type": "proc", "source": "proc"},
        {
            "destination": "/dev",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "strictatime", "mode=755", "size=128m"],
        },
        {
            "destination": "/dev/pts",
            "type": "devpts",
            "source": "devpts",
            "options": ["nosuid", "noexec", "newinstance", "ptmxmode=0666", "mode=0620", "gid=5"],
        },
        {
            "destination": "/dev/shm",
            "type": "tmpfs",
            "source": "shm",
            "options": ["nosuid", "noexec", "nodev", "mode=1777", "size=128m"],
        },
        {"destination": "/dev/mqueue", "type": "mqueue", "source": "mqueue"},
        # Android's debuggable console service otherwise opens the host's
        # global character device (major 5, minor 1) and races Linux getty for
        # the physical COM3 UART. A headless sidecar has no interactive
        # console, so terminate console I/O at /dev/null instead.
        bind_mount("/dev/null", "/dev/console"),
        {
            "destination": "/sys",
            "type": "sysfs",
            "source": "sysfs",
            "options": ["nosuid", "noexec", "nodev", "rw"],
        },
        {
            "destination": "/sys/fs/cgroup",
            "type": "cgroup",
            "source": "cgroup",
            "options": ["nosuid", "noexec", "nodev", "relatime", "rw"],
        },
        bind_mount("/run/binderfs/binder", "/dev/binder"),
        bind_mount("/run/binderfs/hwbinder", "/dev/hwbinder"),
        bind_mount("/run/binderfs/vndbinder", "/dev/vndbinder"),
        bind_mount("/run/aco-ipc", "/run/aco-ipc"),
        bind_mount(data_dir, "/data"),
    ]
    namespaces = [
        {"type": "pid"},
        {"type": "ipc"},
        {"type": "uts"},
        {"type": "mount"},
        {"type": "cgroup"},
    ]
    if not share_host_network:
        namespaces.insert(1, {"type": "network"})

    return {
        "ociVersion": "1.2.0",
        "process": {
            "terminal": False,
            "user": {"uid": 0, "gid": 0},
            "args": [
                "/init",
                "qemu=1",
                "androidboot.hardware=redroid",
                "androidboot.use_memfd=1",
                "androidboot.redroid_gpu_mode=guest",
                "androidboot.redroid_width=480",
                "androidboot.redroid_height=320",
                "androidboot.redroid_dpi=160",
                "androidboot.redroid_fps=10",
            ],
            "env": [
                "PATH=/product/bin:/apex/com.android.runtime/bin:/apex/com.android.art/bin:/system_ext/bin:/system/bin:/system/xbin:/vendor/bin",
                "ANDROID_ROOT=/system",
                "ANDROID_DATA=/data",
            ],
            "cwd": "/",
            "capabilities": capabilities,
            "noNewPrivileges": False,
        },
        "root": {"path": rootfs, "readonly": False},
        "hostname": "aco-android-sidecar",
        "mounts": mounts,
        "linux": {
            "rootfsPropagation": "rprivate",
            "maskedPaths": [],
            "readonlyPaths": [],
            "namespaces": namespaces,
            "devices": [
                device("/dev/null", 1, 3),
                device("/dev/zero", 1, 5),
                device("/dev/full", 1, 7),
                device("/dev/random", 1, 8),
                device("/dev/urandom", 1, 9),
                device("/dev/tty", 5, 0),
            ],
            "resources": {
                "devices": [{"allow": True, "access": "rwm"}],
                "memory": {"limit": memory_bytes},
                "pids": {"limit": 2048},
            },
            "cgroupsPath": "/aco-android-sidecar",
        },
        "annotations": {
            "org.opencontainers.image.ref.name": "redroid/redroid:12.0.0_64only-latest",
            "org.opencontainers.image.digest": "sha256:3c7f9450188226bf8042c0159b9b38abe2106f1ceb0dfa45fae1cbc6409cd9bb",
            "org.edgelvef.runtime.network": (
                "shared-board-network" if share_host_network else "isolated-no-host-port"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--rootfs", default="../rootfs")
    parser.add_argument("--data-dir", default="/opt/aco-sidecar/data/android12")
    parser.add_argument("--memory-mib", type=int, default=1024)
    parser.add_argument(
        "--share-host-network",
        action="store_true",
        help="Run Android in the board network namespace so its Wi-Fi HAL can own IW612.",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    config = make_config(
        args.rootfs,
        args.data_dir,
        args.memory_mib * 1024 * 1024,
        share_host_network=args.share_host_network,
    )
    output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
