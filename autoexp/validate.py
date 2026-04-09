"""Validation pipeline: AST + compile + locked/editable file checks."""

import ast
import subprocess
import sys
import tempfile
from fnmatch import fnmatch
from pathlib import Path


def _matches_any_glob(filepath: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch(filepath, pattern):
            return True
    return False


def _py_compile_check(filepath: str) -> tuple[bool, str]:
    """Non-destructive compile check via subprocess (sica pattern)."""
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / Path(filepath).name
            tmp.write_text(Path(filepath).read_text())
            r = subprocess.run(
                [sys.executable, "-m", "py_compile", str(tmp)],
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode != 0:
                return False, r.stderr.strip()[:500]
            return True, "ok"
    except Exception as e:
        return False, str(e)


def validate_files(file_paths: list[str], config: dict) -> tuple[bool, str]:
    """Validate files against config rules and syntax.

    Returns (ok, reason).
    """
    editable = config.get("editable_files", ["*"])
    locked = config.get("locked_files", [])

    for filepath in file_paths:
        # Check locked
        if _matches_any_glob(filepath, locked):
            return False, f"locked:{filepath}"

        # Check editable
        if editable != ["*"] and not _matches_any_glob(filepath, editable):
            return False, f"not_editable:{filepath}"

        if not Path(filepath).exists():
            return False, f"not_found:{filepath}"

        # Python files: syntax + compile
        if filepath.endswith(".py"):
            content = Path(filepath).read_text()
            try:
                ast.parse(content)
            except SyntaxError as e:
                return False, f"syntax_error:{filepath}:{e.msg}:{e.lineno}"

            ok, reason = _py_compile_check(filepath)
            if not ok:
                return False, f"compile_error:{filepath}:{reason}"

    return True, "ok"
