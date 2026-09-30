"""Extract text from an opinion PDF in a sandboxed subprocess (rlimits,
timeout, no network namespace when available, no core dumps). The PDF
comes from a public source but is still parsed as untrusted input.

Worker mode:  python -I -m cp_ingest.pdftext   (PDF on stdin, JSON on stdout)
"""

from __future__ import annotations

import json
import resource
import shutil
import subprocess  # nosec B404 - fixed argv
import sys
import tempfile

MAX_PAGES = 400


def _worker() -> None:
    import pypdfium2 as pdfium

    data = sys.stdin.buffer.read()
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError:
        print(json.dumps({"ok": False, "reason": "unreadable"}))
        return
    if len(pdf) > MAX_PAGES:
        print(json.dumps({"ok": False, "reason": "too_many_pages"}))
        return
    pages = []
    for i in range(len(pdf)):
        t = pdf[i].get_textpage().get_text_range().replace("\r\n", "\n").replace("\r", "\n")
        pages.append(t.strip())
    print(json.dumps({"ok": True, "text": "\n\n".join(p for p in pages if p), "pages": len(pdf)}))


def extract(data: bytes, timeout: int = 60, mem: int = 1 << 30) -> dict:
    jobdir = tempfile.mkdtemp(prefix="cp-pdf-")

    def pre():
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 5))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    argv = [sys.executable, "-I", "-m", "cp_ingest.pdftext"]
    unshare = shutil.which("unshare")
    if unshare and subprocess.run([unshare, "-n", "true"], capture_output=True).returncode == 0:  # nosec B603
        argv = [unshare, "-n", *argv]
    env = {"PATH": "/usr/bin:/bin", "TMPDIR": jobdir, "HOME": jobdir}
    try:
        p = subprocess.run(argv, input=data, capture_output=True, timeout=timeout, env=env,  # nosec B603
                           preexec_fn=pre, cwd=jobdir)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout"}
    finally:
        shutil.rmtree(jobdir, ignore_errors=True)
    if p.returncode != 0:
        return {"ok": False, "reason": "worker_failed"}
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"ok": False, "reason": "bad_output"}


if __name__ == "__main__":
    _worker()
