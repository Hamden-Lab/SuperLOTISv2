"""Scheduler parser utilities.

Functions to fetch schedule text from a scheduler UDP server and to parse
schedule lines into a mapping from datetimes to command dictionaries.

Supported line formats:
- NOW [delta_seconds] [computer] [device] [command ...]
- sec min hour day month year [delta_seconds] [computer] [device] [command ...]

If a time collides (multiple lines same datetime) the values are appended
to a list for that datetime.
"""
from __future__ import annotations

import socket
import datetime
from typing import Dict, List, Optional, Tuple


SCHEDULER_QUERY = "/all"


def fetch_schedule_text(host: str, port: int, timeout: float = 2.0) -> Optional[str]:
    """Query a scheduler UDP server and return the text response.

    Returns None on error.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(SCHEDULER_QUERY.encode("utf-8"), (host, port))
            data, _ = sock.recvfrom(65536)
            return data.decode("utf-8", errors="replace")
    except Exception:
        return None


def _try_parse_int(token: str) -> Optional[int]:
    try:
        return int(token)
    except Exception:
        return None


def parse_schedule_text(text: str, base_dt: Optional[datetime.datetime] = None) -> Dict[datetime.datetime, List[dict]]:
    """Parse schedule text into a dict mapping datetimes to list of commands.

    Each returned value is a dict with keys: ``computer``, ``device``, ``command`` (string)
    """
    if base_dt is None:
        base_dt = datetime.datetime.now()

    result: Dict[datetime.datetime, List[dict]] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        tokens = line.split()
        if not tokens:
            continue

        # Format A: NOW [delta_seconds] computer device ...
        if tokens[0].upper() == "NOW":
            # tokens[1] might be delta seconds
            delta = 0
            idx = 1
            if len(tokens) > 1 and _try_parse_int(tokens[1]) is not None:
                delta = int(tokens[1])
                idx = 2

            scheduled = base_dt + datetime.timedelta(seconds=delta)
            rest = tokens[idx:]

        else:
            # Format B: sec min hour day month year [delta_seconds] computer device ...
            if len(tokens) < 6:
                # not enough tokens to form a timestamp; skip
                continue
            vals = [_try_parse_int(t) for t in tokens[:6]]
            if any(v is None for v in vals):
                # fallback: try to interpret first token as seconds offset from base_dt
                first = _try_parse_int(tokens[0])
                if first is None:
                    continue
                scheduled = base_dt + datetime.timedelta(seconds=first)
                rest = tokens[1:]
            else:
                sec, minute, hour, day, month, year = vals  # type: ignore
                try:
                    scheduled = datetime.datetime(year, month, day, hour, minute, sec)
                except Exception:
                    # invalid date, skip
                    continue

                # optional delta seconds after the six time fields
                idx = 6
                delta = 0
                if len(tokens) > 6 and _try_parse_int(tokens[6]) is not None:
                    delta = int(tokens[6])
                    idx = 7
                if delta:
                    scheduled = scheduled + datetime.timedelta(seconds=delta)
                rest = tokens[idx:]

        if len(rest) < 2:
            # need at least computer + device
            continue

        computer = rest[0]
        device = rest[1]
        command = " ".join(rest[2:]) if len(rest) > 2 else ""

        entry = {"computer": computer, "device": device, "command": command, "line": line}

        # normalize scheduled to second precision (drop microseconds)
        scheduled = scheduled.replace(microsecond=0)

        result.setdefault(scheduled, []).append(entry)

    return result


if __name__ == "__main__":
    # tiny manual test
    sample = """
    now 0 SLOTIS PDU poweron 2
    30 0 12 1 1 2026 0 LYMAN CAMERA EXPOSE"""
    for when, entries in parse_schedule_text(sample).items():
        print(when.isoformat(), entries)
