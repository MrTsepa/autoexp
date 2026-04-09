"""Training runner with timeout and abort monitoring."""

import re
import signal
import subprocess
import time
from typing import Callable, NamedTuple


class TrainResult(NamedTuple):
    status: str  # completed, timeout, aborted, crashed
    exit_code: int | None
    duration_seconds: float
    stdout_tail: str  # last N lines
    abort_reason: str | None


def _parse_timeout(s: str) -> int:
    """Parse timeout string like '20m', '2h', '30s' to seconds."""
    s = s.strip().lower()
    if s.endswith("h"):
        return int(float(s[:-1]) * 3600)
    if s.endswith("m"):
        return int(float(s[:-1]) * 60)
    if s.endswith("s"):
        return int(float(s[:-1]))
    return int(s)


def _check_abort_rules(line: str, rules: list[dict], line_num: int) -> str | None:
    """Check a line against abort rules. Returns abort reason or None."""
    for rule in rules:
        after_lines = rule.get("after_lines", 0)
        if line_num < after_lines:
            continue

        pattern = rule.get("pattern", "")
        match = re.search(pattern, line)
        if not match:
            continue

        # Try to extract a numeric value after the pattern
        value_match = re.search(rf"{pattern}\s*[=:]\s*([\d.eE+-]+)", line)
        if not value_match:
            continue

        try:
            value = float(value_match.group(1))
        except ValueError:
            continue

        condition = rule.get("condition", "below")
        threshold = rule.get("threshold", 0.0)

        if condition == "below" and value < threshold:
            return f"{pattern}={value} < {threshold}"
        if condition == "above" and value > threshold:
            return f"{pattern}={value} > {threshold}"

    return None


def run_training(
    command: str,
    timeout: str | int | None = None,
    abort_rules: list[dict] | None = None,
    on_line: Callable[[str], None] | None = None,
    tail_size: int = 100,
) -> TrainResult:
    """Run a training command with timeout and abort monitoring."""
    timeout_secs = _parse_timeout(str(timeout)) if timeout else None
    abort_rules = abort_rules or []
    tail: list[str] = []
    line_num = 0
    abort_reason = None

    start = time.time()
    proc = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN),
    )

    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            line_num += 1
            tail.append(line)
            if len(tail) > tail_size:
                tail.pop(0)

            if on_line:
                on_line(line)

            # Check abort rules
            reason = _check_abort_rules(line, abort_rules, line_num)
            if reason:
                abort_reason = reason
                proc.terminate()
                proc.wait(timeout=10)
                break

            # Check timeout
            if timeout_secs and (time.time() - start) > timeout_secs:
                abort_reason = f"timeout after {timeout_secs}s"
                proc.terminate()
                proc.wait(timeout=10)
                break
        else:
            proc.wait()
    except Exception:
        proc.kill()
        proc.wait()

    duration = time.time() - start

    if abort_reason and "timeout" in abort_reason:
        status = "timeout"
    elif abort_reason:
        status = "aborted"
    elif proc.returncode != 0:
        status = "crashed"
    else:
        status = "completed"

    return TrainResult(
        status=status,
        exit_code=proc.returncode,
        duration_seconds=round(duration, 1),
        stdout_tail="\n".join(tail),
        abort_reason=abort_reason,
    )
