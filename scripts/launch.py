"""Start the API, the analysis worker and the web UI together.

    start.cmd [--no-browser]

Waits until the health check reports ok, opens the browser, and stops all
three processes on Ctrl+C (or when any one of them exits).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VITE = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
IS_WINDOWS = os.name == "nt"


def say(msg: str) -> None:
    print(f"[start] {msg}", flush=True)


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return True
    return False


def fetch(url: str) -> tuple[int, bytes] | None:
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError):
        return None


class KillOnCloseJob:
    """Windows Job Object that kills every assigned process (and their
    children) when the launcher exits for any reason, including being killed
    from Task Manager, so no orphaned server keeps holding a port."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits),
                        ("IoInfo", ctypes.c_uint64 * 6),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
        k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int,
                                                wintypes.LPVOID, wintypes.DWORD)
        k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        self._k32 = k32
        self._job = k32.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self._job or not k32.SetInformationJobObject(
                self._job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):  # 9: extended limits
            raise OSError(ctypes.get_last_error(), "job object setup failed")

    def assign(self, proc: subprocess.Popen) -> None:
        if not self._k32.AssignProcessToJobObject(self._job, int(proc._handle)):  # type: ignore[attr-defined]
            say(f"uyarı: süreç {proc.pid} iş nesnesine eklenemedi")


def make_job() -> KillOnCloseJob | None:
    if not IS_WINDOWS:
        return None
    try:
        return KillOnCloseJob()
    except OSError as exc:  # best effort; Ctrl+C shutdown still works without it
        say(f"uyarı: Windows iş nesnesi oluşturulamadı ({exc})")
        return None



def spawn(name: str, cmd: list[str], cwd: Path, env: dict[str, str],
          job: KillOnCloseJob | None) -> subprocess.Popen:
    # Own process group per child: the launcher forwards Ctrl+C as Ctrl+Break
    # so every child shuts down gracefully, even when stopped individually.
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=flags)
    if job is not None:
        job.assign(proc)

    def pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(f"[{name}] {line.rstrip()}", flush=True)

    threading.Thread(target=pump, name=f"pump-{name}", daemon=True).start()
    return proc


def stop_all(procs: dict[str, subprocess.Popen], timeout: float = 10) -> None:
    for proc in procs.values():
        if proc.poll() is None:
            try:
                if IS_WINDOWS:
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.send_signal(signal.SIGINT)
            except OSError:
                pass
    deadline = time.monotonic() + timeout
    for name, proc in procs.items():
        try:
            proc.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            say(f"{name} zamanında durmadı; zorla kapatılıyor")
            proc.kill()
            proc.wait()


def wait_until_ready(procs: dict[str, subprocess.Popen], api_url: str, web_url: str,
                     timeout: float) -> str | None:
    """Returns None when ready, otherwise a reason."""
    deadline = time.monotonic() + timeout
    last_status = None
    while time.monotonic() < deadline:
        for name, proc in procs.items():
            if proc.poll() is not None:
                return f"{name} başlatılırken kapandı (çıkış kodu {proc.returncode})"
        health = fetch(f"{api_url}/api/v1/health")
        if health and health[0] == 200:
            body = json.loads(health[1])
            last_status = body.get("status")
            web = fetch(web_url)
            if last_status == "ok" and web and web[0] == 200:
                return None
        time.sleep(0.5)
    return f"{timeout:.0f} sn içinde hazır olmadı (son sağlık durumu: {last_status})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Start MMA Fight Analyzer")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    parser.add_argument("--timeout", type=float, default=120, help="startup timeout (s)")
    args = parser.parse_args()

    api_port = int(os.environ.get("FA_API_PORT", "8000"))
    web_port = int(os.environ.get("FA_WEB_PORT", "5173"))
    node = shutil.which("node")
    problems = []
    if node is None:
        problems.append("Node.js PATH üzerinde bulunamadı.")
    if not VITE.exists():
        problems.append("Arayüz paketleri eksik; setup.cmd çalıştırın.")
    for label, port, var in (("API", api_port, "FA_API_PORT"), ("Web", web_port, "FA_WEB_PORT")):
        if port_in_use(port):
            problems.append(f"{label} portu {port} kullanımda (uygulama zaten açık olabilir). "
                            f"Kapatın ya da {var} ile başka bir port seçin.")
    if problems:
        for p in problems:
            say(f"HATA: {p}")
        return 1

    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8",
           "FA_API_PORT": str(api_port), "FA_WEB_PORT": str(web_port)}
    api_url = f"http://127.0.0.1:{api_port}"
    web_url = f"http://127.0.0.1:{web_port}"

    job = make_job()
    procs: dict[str, subprocess.Popen] = {}
    try:
        procs["api"] = spawn("api", [sys.executable, "-m", "uvicorn",
                                     "fight_analyzer.api.app:create_app", "--factory",
                                     "--host", "127.0.0.1", "--port", str(api_port),
                                     "--no-access-log"], BACKEND, env, job)
        procs["worker"] = spawn("worker", [sys.executable, "-m", "fight_analyzer.jobs"],
                                BACKEND, env, job)
        procs["web"] = spawn("web", [node, str(VITE), "--clearScreen", "false"],  # type: ignore[list-item]
                             FRONTEND, env, job)

        say("API, analiz işçisi ve arayüz başlatılıyor ...")
        if reason := wait_until_ready(procs, api_url, web_url, args.timeout):
            say(f"HATA: {reason}")
            return 1

        print(flush=True)
        say("MMA Fight Analyzer hazır")
        say(f"  Arayüz   {web_url}")
        say(f"  Sağlık   {api_url}/api/v1/health")
        say(f"  API şeması {api_url}/api/openapi.json")
        say("  Durdurmak için Ctrl+C.")
        print(flush=True)
        if not args.no_browser:
            webbrowser.open(web_url)

        while True:
            for name, proc in procs.items():
                if proc.poll() is not None:
                    say(f"HATA: {name} beklenmedik şekilde kapandı (çıkış kodu {proc.returncode})")
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        say("durduruluyor ...")
        return 0
    finally:
        stop_all(procs)
        say("durduruldu")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    if IS_WINDOWS:  # Ctrl+Break stops everything cleanly, like Ctrl+C
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    sys.exit(main())
