"""Run local PowerShell commands and stop their process tree on cancellation."""
from base64 import b64encode
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryFile
import time

import win32api
import win32job


BOOTSTRAP = """
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$code = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::ReadLine()))
& ([ScriptBlock]::Create($code))
if ($null -ne $LASTEXITCODE) { exit $LASTEXITCODE }
"""


def run_powershell(command, cwd, check_cancel):
    executable = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    payload = b64encode(command.encode("utf-8")) + b"\n"
    env = {key: value for key, value in os.environ.items() if key.upper() not in {"OPENAI_API_KEY", "GEMINI_API_KEY"}}
    with TemporaryFile() as output, ExitStack() as handles:
        job = win32job.CreateJobObject(None, "")
        handles.callback(job.Close)
        limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        limits["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
        with subprocess.Popen(
            [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", BOOTSTRAP],
            cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ) as process:
            try:
                # The wrapper waits for stdin, so user code cannot run before the job is assigned.
                handle = win32api.OpenProcess(0x0101, False, process.pid)
                try:
                    win32job.AssignProcessToJobObject(job, handle)
                finally:
                    handle.Close()
                check_cancel()
                deadline = time.monotonic() + 45
                try:
                    process.communicate(payload, timeout=0.2)
                except subprocess.TimeoutExpired:
                    while process.poll() is None:
                        check_cancel()
                        if time.monotonic() >= deadline:
                            raise TimeoutError("El comando superó 45 segundos.")
                        try:
                            process.communicate(timeout=0.2)
                        except subprocess.TimeoutExpired:
                            continue
            finally:
                # Terminate children that are still running, even if PowerShell already exited.
                try:
                    win32job.TerminateJobObject(job, 1)
                finally:
                    if process.poll() is None:
                        process.kill()
            output.seek(0)
            data = output.read(32001)
            return {"exit_code": process.returncode, "output": data[:32000].decode("utf-8", errors="replace"), "truncated": len(data) > 32000}
