#!/usr/bin/env python3
"""pexpect wrapper for board SSH/SCP with interactive sudo support.

Usage:
  lara_ssh.py ssh "<cmd>" [timeout_s]        # non-interactive remote command
  lara_ssh.py scp <src> <dst> [-r]           # file/dir transfer
  lara_ssh.py run "<cmd>"                    # pty (-tt) session answering sudo

Password comes from env LARA_BOARD_PW — never write it to any file.
Board host is configured below; adjust per project.

Hard-won details embedded here (do not "simplify" them away):
  - sudo over ssh needs a tty: run_interactive uses ssh -tt.
  - expect pattern for the sudo prompt MUST escape the brackets:
    "\\[sudo\\] password" — unescaped [sudo] is a character class and
    never matches the real prompt.
  - The password is sent with logfile_read disabled so it is never
    echoed into transcripts; the pty itself does not echo it either.
  - Long runs need line buffering (sys.stdout.reconfigure), otherwise
    background-task output files stay empty until exit.
  - scp arg order is scp <src> <dst> [-r]; passing a directory as dst
    that already exists nests one level.
"""
import os
import sys
import time

import pexpect

HOST = "ubuntu@192.168.2.100"
PASSWORD = os.environ.get("LARA_BOARD_PW", "")


def handle_auth(child) -> None:
    idx = child.expect(["[Pp]assword:", pexpect.EOF, pexpect.TIMEOUT], timeout=30)
    if idx == 0:
        child.sendline(PASSWORD)
    elif idx == 2:
        print("AUTH TIMEOUT", file=sys.stderr)
        sys.exit(3)


def run_ssh(cmd: str, timeout: int = 600) -> int:
    child = pexpect.spawn(
        "ssh", ["-F", "/dev/null", "-o", "StrictHostKeyChecking=accept-new",
                HOST, cmd],
        encoding="utf-8", timeout=timeout,
    )
    handle_auth(child)
    child.logfile_read = sys.stdout
    child.expect(pexpect.EOF)
    return child.exitstatus or 0


def run_scp(src: str, dst: str, recursive: bool = False, timeout: int = 3600) -> int:
    args = ["-F", "/dev/null", "-o", "StrictHostKeyChecking=accept-new"]
    if recursive:
        args.append("-r")
    args += [src, f"{HOST}:{dst}"]
    child = pexpect.spawn("scp", args, encoding="utf-8", timeout=timeout)
    handle_auth(child)
    child.logfile_read = sys.stdout
    child.expect(pexpect.EOF)
    return child.exitstatus or 0


def run_interactive(cmd: str, total_timeout: int = 7200, chunk_timeout: int = 900) -> int:
    """Run cmd over ssh with a forced pty (-tt), answering sudo password prompts."""
    child = pexpect.spawn(
        "ssh", ["-tt", "-F", "/dev/null", "-o", "StrictHostKeyChecking=accept-new",
                HOST, cmd],
        encoding="utf-8", timeout=chunk_timeout,
    )
    handle_auth(child)
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    child.logfile_read = sys.stdout
    deadline = time.time() + total_timeout
    while True:
        idx = child.expect(["\\[sudo\\] password", pexpect.EOF, pexpect.TIMEOUT])
        if idx == 0:
            child.logfile_read = None  # never echo the password back
            child.sendline(PASSWORD)
            time.sleep(0.3)
            child.logfile_read = sys.stdout
        elif idx == 1:
            return child.exitstatus or 0
        else:
            if time.time() > deadline:
                print("RUN TIMEOUT", file=sys.stderr)
                return 4
            print("[still running...]", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "ssh":
        sys.exit(run_ssh(sys.argv[2], timeout=int(sys.argv[3]) if len(sys.argv) > 3 else 600))
    elif mode == "scp":
        sys.exit(run_scp(sys.argv[2], sys.argv[3],
                         recursive=(len(sys.argv) > 4 and sys.argv[4] == "-r")))
    elif mode == "run":
        sys.exit(run_interactive(sys.argv[2]))
    else:
        print("usage: lara_ssh.py ssh <cmd> [timeout] | scp <src> <dst> [-r] | run <cmd>",
              file=sys.stderr)
        sys.exit(2)
