"""Git operations for autoexp."""

import subprocess


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def ensure_clean() -> tuple[bool, str]:
    r = _git("status", "--porcelain", check=False)
    # Filter out .autoexp/ changes (DB writes are OK)
    dirty = [
        line for line in r.stdout.strip().splitlines()
        if line and not line.endswith(".autoexp/experiments.db")
        and not line.endswith(".autoexp/experiments.db-journal")
    ]
    if dirty:
        return False, f"dirty working tree:\n" + "\n".join(dirty)
    return True, "clean"


def get_head_sha() -> str:
    r = _git("rev-parse", "HEAD", check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def get_changed_files() -> list[str]:
    r = _git("diff", "--name-only", "HEAD", check=False)
    staged = _git("diff", "--name-only", "--cached", check=False)
    untracked = _git("ls-files", "--others", "--exclude-standard", check=False)
    files = set()
    for output in (r.stdout, staged.stdout, untracked.stdout):
        for line in output.strip().splitlines():
            if line:
                files.add(line)
    return sorted(files)


def commit(message: str, files: list[str] | None = None) -> str:
    if files:
        _git("add", *files)
    else:
        _git("add", "-A")
    _git("commit", "-m", message)
    return get_head_sha()


def revert_head() -> tuple[bool, str]:
    r = _git("revert", "HEAD", "--no-edit", check=False)
    if r.returncode != 0:
        return False, r.stderr.strip()
    return True, get_head_sha()
