#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys


DENY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Network / exfil primitives
    (re.compile(r"\bcurl\b"), "network exfil via curl"),
    (re.compile(r"\bwget\b"), "network exfil via wget"),
    (re.compile(r"\bnc\b"), "network exfil via netcat"),
    (re.compile(r"\bncat\b"), "network exfil via ncat"),
    (re.compile(r"\bsocat\b"), "network exfil via socat"),
    (re.compile(r"\bssh\b"), "network exfil via ssh"),
    (re.compile(r"\bscp\b"), "network exfil via scp"),
    (re.compile(r"\bsftp\b"), "network exfil via sftp"),
    (re.compile(r"\btelnet\b"), "network exfil via telnet"),
    # Obvious "download and execute" chains
    (re.compile(r"\|\s*(bash|sh)\b"), "piped shell execution"),
    (re.compile(r"\b(bash|sh)\s+-c\b"), "shell -c execution"),
    # High-signal attempts to print environment
    (re.compile(r"(^|\s)env($|\s)"), "printing environment"),
    (re.compile(r"\bprintenv\b"), "printing environment"),
    (re.compile(r"/proc/(self|\d+)/environ"), "reading process environment"),
    # Prevent using GitHub CLI for token operations
    (re.compile(r"\bgh\b"), "GitHub CLI usage disabled"),
    # Prevent pushing / modifying remotes
    (re.compile(r"\bgit\s+push\b"), "pushing is disabled"),
    (re.compile(r"\bgit\s+remote\s+set-url\b"), "editing git remotes is disabled"),
]


def _deny(reason: str) -> None:
    print(json.dumps({"decision": "deny", "reason": reason}))


def _allow() -> None:
    print(json.dumps({"decision": "allow"}))


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        _allow()
        return

    tool_input = event.get("tool_input") or {}
    command = str(tool_input.get("command") or "")

    # If this is a follow-up input to a running process, we can't reliably
    # inspect intent. Allow.
    if tool_input.get("is_input") is True:
        _allow()
        return

    for pattern, reason in DENY_PATTERNS:
        if pattern.search(command):
            _deny(reason)
            return

    _allow()


if __name__ == "__main__":
    main()
