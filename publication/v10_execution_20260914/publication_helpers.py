"""Credential checks and isolated Git operations for the v10 publication."""

import os
import re
import subprocess
from pathlib import Path

KEY_FILE = Path("/mnt/afs/260010168/.config/disastertrace/deepseek_followup_20260914.key")
SSH = (
    "ssh -i /mnt/afs/260010168/.ssh/github_ed25519 -o IdentitiesOnly=yes "
    "-o BatchMode=yes -o StrictHostKeyChecking=yes "
    "-o UserKnownHostsFile=/mnt/afs/260010168/.ssh/github_review_known_hosts "
    "-o ConnectTimeout=15"
)
SENSITIVE = {
    "api_token": re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bearer_value": re.compile(rb"(?i)Bearer\s+[A-Za-z0-9._~+/-]{24,}"),
    "signed_url": re.compile(
        rb"(?i)[?&](?:X-Amz-Signature|Signature|Key-Pair-Id|GoogleAccessId)="
    ),
    "jwt": re.compile(
        rb"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{40,}"
    ),
}


def inspect_payload(name, content, private_values=()):
    path = Path(name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or any(c in name for c in "\n\r\t\0")
        or any(
            part in {".git", ".ssh", ".config", ".venv", "__pycache__"}
            for part in path.parts
        )
        or path.suffix in {".key", ".pem"}
        or path.name.startswith(".env")
    ):
        raise ValueError("Excluded publication path: " + name)
    if len(content) >= 90 * 1024 * 1024:
        raise ValueError("Publication file exceeds size ceiling: " + name)
    for label, pattern in SENSITIVE.items():
        if pattern.search(content):
            raise ValueError("Credential or signed-URL pattern " + label + " in " + name)
    if any(value and value in content for value in private_values):
        raise ValueError("Known private credential found in " + name)


def git_runner(bare):
    env = dict(
        os.environ,
        GIT_SSH_COMMAND=SSH,
        GIT_TERMINAL_PROMPT="0",
        GIT_OPTIONAL_LOCKS="0",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Codex",
        GIT_AUTHOR_EMAIL="codex@localhost",
        GIT_COMMITTER_NAME="Codex",
        GIT_COMMITTER_EMAIL="codex@localhost",
    )
    for name in [
        "GIT_INDEX_FILE",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_QUARANTINE_PATH",
    ]:
        env.pop(name, None)

    def git(*args, data=None, timeout=600):
        reply = subprocess.run(
            ["git", "-c", "safe.directory=" + str(bare), "--git-dir=" + str(bare), *args],
            env=env,
            input=data,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if reply.returncode:
            raise RuntimeError(
                "Git operation failed: " + args[0] + "; exit=" + str(reply.returncode)
            )
        return reply.stdout

    return git
