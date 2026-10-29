#!/usr/bin/env python3
"""Go to the next or previous workspace by number: 1 -> 2 -> 3 ... and back, also to an empty one (it is created,
like pressing SUPER+2). Stops at 1 and at 10. The touchpad's three-finger swipe runs this (Gestures.sh).

  Workspace.py next   the workspace with the next number
  Workspace.py prev   the workspace with the previous number
"""
import json
import re
import subprocess
import sys

FIRST, LAST = 1, 10


def i3(*args):
    try:
        return subprocess.run(["i3-msg"] + list(args), capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def name_for(num):
    """The name the i3 config gives workspace `num` (set $ws2 "2:II"), so a new one looks like SUPER+2 made it."""
    out = i3("-t", "get_config")
    try:
        config = json.loads(out).get("config", "")      # (the raw reply, from an i3-msg that does not unwrap it)
    except (ValueError, AttributeError):
        config = out                                    # i3-msg prints the config text itself
    m = re.search(r'^[ \t]*set[ \t]+\$ws%d[ \t]+"?([^"\n]*?)"?[ \t]*$' % num, config, re.M)
    name = m.group(1) if m else ""
    # only a plain "2" or "2:something" without quotes or backslashes goes into the i3 command
    return name if re.fullmatch(r'%d(:[^"\\]{1,40})?' % num, name) else str(num)


def main(argv):
    if len(argv) != 1 or argv[0] not in ("next", "prev"):
        print(__doc__.strip())
        return 2
    try:
        spaces = json.loads(i3("-t", "get_workspaces") or "[]")
    except ValueError:
        return 1
    if not isinstance(spaces, list):
        return 1
    cur = next((w for w in spaces if isinstance(w, dict) and w.get("focused")), None)
    if cur is None:
        return 1
    num = cur.get("num") if isinstance(cur.get("num"), int) else -1
    if num < FIRST:                                     # a workspace without a number: start from the first
        want = FIRST
    else:
        want = num + 1 if argv[0] == "next" else num - 1
    if not FIRST <= want <= LAST or want == num:
        return 0
    if any(isinstance(w, dict) and w.get("num") == want for w in spaces):
        i3("workspace number %d" % want)                # it exists (whatever its name)
    else:
        i3('workspace number "%s"' % name_for(want))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
