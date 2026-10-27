"""Helpers shared by the skill runners."""
import subprocess
from pathlib import Path

from ..config import settings


def run_script(cmd):
    """Run a build script; on failure raise with its last output line."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        lines = [l for l in (r.stdout + r.stderr).strip().splitlines() if l.strip()]
        raise RuntimeError(lines[-1] if lines else f"{Path(cmd[1]).name} failed")
    return r.stdout


def result_name(label):
    """File name of the result (without extension), e.g. "დავალება 3 - <name>"."""
    return f"დავალება {label} - {settings.student_name}"


def header_args(course):
    """Student header data for the build scripts (comes from .env, never from code)."""
    return ["--student", settings.student_name, "--group", settings.student_group, "--course", course]
