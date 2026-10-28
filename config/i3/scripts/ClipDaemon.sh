#!/usr/bin/env bash
# Start whichever clipboard manager is installed: clipmenu (preferred) or CopyQ (Fedora has no clipmenu package).
if command -v clipmenud >/dev/null 2>&1; then exec clipmenud
elif command -v copyq >/dev/null 2>&1; then exec copyq --start-server
fi
