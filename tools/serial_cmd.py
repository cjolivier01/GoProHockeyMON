#!/usr/bin/env python3
"""Send one firmware serial command using a low-level termios tty open."""

from __future__ import annotations

import argparse
import fcntl
import os
import select
import sys
import termios
import time
import tty


BAUD_RATES = {
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
    230400: termios.B230400,
    460800: termios.B460800,
    921600: termios.B921600,
}


def configure_port(fd: int, baud: int) -> None:
    attrs = termios.tcgetattr(fd)
    tty.setraw(fd, termios.TCSANOW)
    attrs = termios.tcgetattr(fd)
    baud_flag = BAUD_RATES.get(baud)
    if baud_flag is None:
        raise ValueError(f"Unsupported baud rate for termios helper: {baud}")
    attrs[4] = baud_flag
    attrs[5] = baud_flag
    attrs[2] |= termios.CLOCAL | termios.CREAD
    attrs[2] &= ~termios.HUPCL
    attrs[3] &= ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def clear_modem_reset_lines(fd: int) -> None:
    mask = 0
    for name in ("TIOCM_DTR", "TIOCM_RTS"):
        mask |= getattr(termios, name, 0)
    clear_ioctl = getattr(termios, "TIOCMBIC", None)
    if mask and clear_ioctl is not None:
        try:
            fcntl.ioctl(fd, clear_ioctl, mask.to_bytes(4, sys.byteorder))
        except OSError:
            pass


def read_available(fd: int, max_seconds: float, quiet_after: float, emit: bool) -> bool:
    deadline = time.monotonic() + max_seconds
    last_data: float | None = None
    saw_data = False
    while time.monotonic() < deadline:
        timeout = min(0.05, max(0.0, deadline - time.monotonic()))
        ready, _, _ = select.select([fd], [], [], timeout)
        if ready:
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                chunk = b""
            if chunk:
                saw_data = True
                last_data = time.monotonic()
                if emit:
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                continue
        if last_data is not None and time.monotonic() - last_data >= quiet_after:
            break
    return saw_data


def drain_until_quiet(fd: int, max_seconds: float, quiet_after: float) -> None:
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        saw_data = read_available(fd, min(quiet_after, deadline - time.monotonic()), quiet_after, False)
        if not saw_data:
            return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", help="firmware command to send, for example 'status'")
    parser.add_argument("--port", required=True, help="serial port")
    parser.add_argument("--baud", type=int, default=115200, help="baud rate")
    parser.add_argument("--timeout", type=float, default=4.0, help="maximum seconds to read")
    parser.add_argument("--quiet-after", type=float, default=0.5, help="stop after this many quiet seconds")
    parser.add_argument("--pre-drain", type=float, default=1.5, help="maximum seconds to drain old logs")
    args = parser.parse_args()

    fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure_port(fd, args.baud)
        clear_modem_reset_lines(fd)
        termios.tcflush(fd, termios.TCIFLUSH)
        drain_until_quiet(fd, args.pre_drain, args.quiet_after)
        os.write(fd, (args.command + "\n").encode("utf-8"))
        read_available(fd, args.timeout, args.quiet_after, True)
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
