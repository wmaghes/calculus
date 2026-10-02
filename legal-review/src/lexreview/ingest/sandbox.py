"""Run the parser worker in a constrained subprocess.

Controls applied to every parse:
* separate process: a parser crash or hang cannot take down the app
* rlimits: address space, CPU seconds, max file size written, open files,
  no core dumps (core dumps would contain document text)
* wall-clock timeout, then SIGKILL
* network: `unshare -n` (empty network namespace) when the host allows it,
  plus an in-process socket guard in the worker
* private TMPDIR per job (OCR temp images), removed after the job
* minimal environment, `python -I` (ignores PYTHON* env vars and user site)
* stderr is captured and discarded, never logged

Production should add a real sandbox (nsjail/bubblewrap/gVisor with
seccomp, read-only root, no /proc access to other processes). Without
`unshare`, the network layer is degraded; that is refused in production.
"""

from __future__ import annotations

import base64
import json
import os
import resource
import shutil
import signal
import subprocess  # nosec B404
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings
from ..errors import ConfigError


@dataclass
class SandboxResult:
    kind: str
    status: str
    reason: str | None
    pages: list[dict]
    meta: dict
    children: list[tuple[str, bytes]]
    sandbox: str


_unshare_ok: bool | None = None


def _can_unshare() -> bool:
    global _unshare_ok
    if _unshare_ok is None:
        exe = shutil.which("unshare")
        if exe is None:
            _unshare_ok = False
        else:
            try:
                r = subprocess.run([exe, "-n", "true"], capture_output=True, timeout=10)  # nosec B603
                _unshare_ok = r.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                _unshare_ok = False
    return _unshare_ok


def _limits(settings: Settings) -> dict:
    return {
        "max_pages": settings.max_pages,
        "max_zip_uncompressed": settings.max_zip_uncompressed,
        "max_zip_ratio": settings.max_zip_ratio,
        "ocr_min_chars": settings.ocr_min_chars,
        "ocr_low_conf": settings.ocr_low_conf,
        "ocr_timeout": 120,
        "max_image_pixels": 100_000_000,
    }


def _run_worker(data: bytes, settings: Settings, work_root: Path, timeout: int, extra: list[str]):
    """Returns (completed_process | None on timeout, isolated)."""
    isolated = _can_unshare()
    if not isolated and settings.production:
        raise ConfigError("parser_network_isolation_unavailable")
    work_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    jobdir = tempfile.mkdtemp(prefix="job-", dir=work_root)
    mem = settings.parse_mem_bytes

    def _preexec():  # runs in the child before exec
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 5))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 30, 1 << 30))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        os.setsid()

    argv = [sys.executable, "-I", "-m", "lexreview.ingest.worker", json.dumps(_limits(settings)), *extra]
    if isolated:
        argv = [shutil.which("unshare"), "-n", *argv]
    env = {"PATH": "/usr/bin:/bin", "TMPDIR": jobdir, "OMP_THREAD_LIMIT": "1", "LANG": "C.UTF-8", "HOME": jobdir}
    try:
        return subprocess.run(  # nosec B603
            argv, input=data, capture_output=True, timeout=timeout, env=env,
            preexec_fn=_preexec, cwd=jobdir,
        ), isolated
    except subprocess.TimeoutExpired:
        return None, isolated
    finally:
        shutil.rmtree(jobdir, ignore_errors=True)


def run_render(data: bytes, page_no: int, settings: Settings, work_root: Path) -> bytes | None:
    """Render one page to PNG inside the sandbox. None if not renderable."""
    proc, _ = _run_worker(data, settings, work_root, 60, [f"render:{int(page_no)}"])
    if proc is None or proc.returncode != 0:
        return None
    try:
        png = json.loads(proc.stdout)["png"]
    except (ValueError, KeyError):
        return None
    return base64.b64decode(png) if png else None


def run_parser(data: bytes, settings: Settings, work_root: Path, timeout: int | None = None) -> SandboxResult:
    timeout = timeout or settings.parse_timeout_s
    proc, isolated = _run_worker(data, settings, work_root, timeout, [])
    if proc is None:
        return SandboxResult("unknown", "timeout", "parse_timeout", [], {}, [], "isolated" if isolated else "degraded")
    # proc.stderr is intentionally dropped: it may contain document text.
    if proc.returncode == -signal.SIGXCPU:
        # CPU-seconds rlimit hit before the wall-clock timeout: same meaning.
        return SandboxResult("unknown", "timeout", "cpu_time_limit", [], {}, [], "isolated" if isolated else "degraded")
    if proc.returncode != 0:
        reason = "worker_killed" if proc.returncode < 0 else "worker_failed"
        return SandboxResult("unknown", "parse_error", reason, [], {}, [], "isolated" if isolated else "degraded")
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        return SandboxResult("unknown", "parse_error", "worker_output_invalid", [], {}, [], "isolated" if isolated else "degraded")
    children = [(name, base64.b64decode(b64)) for name, b64 in out["children"]]
    return SandboxResult(out["kind"], out["status"], out["reason"], out["pages"], out["meta"], children,
                         "isolated" if isolated else "degraded")
