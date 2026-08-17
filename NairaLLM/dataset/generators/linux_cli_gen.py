"""
Linux & CLI Concepts Domain Generator for Dataset A.
Generates comprehensive technical prose on Linux filesystem hierarchy, permissions, systemd, process management, shell pipelines, and cgroups.
"""

from __future__ import annotations

from typing import Any


def get_linux_cli_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "linux_cli",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Linux system administration, CLI utilities, and kernel subsystems",
            },
        })

    add(
        "sem_cli_001",
        "The Filesystem Hierarchy Standard (FHS) defines the standard directory structure and contents in Unix-like operating systems. Essential root directories include: `/bin` and `/usr/bin` for essential user command binaries; `/sbin` and `/usr/sbin` for system administrative binaries; `/etc` for host-specific configuration files; `/var` for variable data files like logs (`/var/log`) and database state; `/tmp` for temporary files; `/dev` for device nodes managed by udev; `/proc` and `/sys` for virtual pseudo-filesystems exposing live kernel and hardware metrics; and `/home` for user home directories.",
        "Linux Filesystem Hierarchy Standard (FHS) directory roles",
    )

    add(
        "sem_cli_002",
        "Unix file permissions control access rights for three distinct classes of users: Owner (u), Group (g), and Others (o). Each class can possess Read (r=4), Write (w=2), and Execute (x=1) permissions, represented as octal numeric modes (e.g., chmod 755 grants rwxr-xr-x). Special permission bits include: SUID (Set User ID, octal 4000), which executes the binary with the file owner's privileges; SGID (Set Group ID, octal 2000), which enforces group inheritance on created files; and the Sticky Bit (octal 1000, chmod +t on `/tmp`), which prevents users from deleting files owned by others.",
        "Unix file permissions, octal notation, and special bits (SUID, SGID, Sticky Bit)",
    )

    add(
        "sem_cli_003",
        "systemd is the modern init system and service manager for Linux operating systems, assuming Process ID 1 (PID 1) during system boot. systemd organizes system services, mount points, sockets, timers, and devices into declarative Unit files (e.g., `app.service`). Key sections in a systemd unit include `[Unit]` (declaring service description and dependencies like `After=network.target`), `[Service]` (declaring `ExecStart`, `Restart=always`, user accounts, and resource limits), and `[Install]` (defining target dependency hooks like `WantedBy=multi-user.target`).",
        "systemd init system architecture and declarative unit file structure",
    )

    add(
        "sem_cli_004",
        "Linux process management relies on POSIX signals for asynchronous inter-process notification. Common signals include SIGINT (Signal 2, triggered via Ctrl+C, graceful termination), SIGTERM (Signal 15, standard termination request allowing cleanup), SIGKILL (Signal 9, immediate uncatchable kernel termination), SIGHUP (Signal 1, hangup signal used by daemons to reload configuration files without restarting), and SIGSEGV (Signal 11, segmentation fault due to illegal memory access). Utilities like `kill`, `pkill`, `top`, and `htop` monitor and manage process trees.",
        "Linux POSIX signals (SIGINT, SIGTERM, SIGKILL, SIGHUP) and process control",
    )

    add(
        "sem_cli_005",
        "Unix shell pipelines connect the standard output (stdout, file descriptor 1) of one command directly to the standard input (stdin, file descriptor 0) of another using anonymous kernel pipes (`|`). Standard error (stderr, file descriptor 2) is redirected separately (e.g., `2>&1` to merge stderr into stdout, or `2>/dev/null` to discard errors). Powerful text processing pipelines combine POSIX core utilities: `grep` for pattern filtering, `sed` for stream editing and substitution, `awk` for columnar record processing, `sort` for ordering, and `uniq -c` for frequency counting.",
        "Shell pipelines, I/O redirection file descriptors, and text processing utilities",
    )

    add(
        "sem_cli_006",
        "Linux Control Groups (cgroups v2) and Namespaces are the foundational kernel technologies enabling containerization platforms like Docker and Podman. Namespaces provide isolated views of system resources for a process tree: PID namespace isolates process IDs; Mount (mnt) namespace isolates filesystem mount points; Network (net) namespace provides private IP interfaces and routing tables; IPC namespace isolates message queues and shared memory; and User namespace maps container root to an unprivileged host UID. cgroups restrict and monitor resource consumption (CPU shares, memory ceilings, I/O bandwidth).",
        "Linux namespaces and cgroups v2 container isolation primitives",
    )

    return samples
