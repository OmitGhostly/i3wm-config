#!/usr/bin/env bash
pid=$(xdotool getwindowfocus getwindowpid 2>/dev/null) || exit 1
name=$(ps -p "$pid" -o comm= 2>/dev/null)
kill -9 "$pid" && notify-send -u low "Terminated" "$name ($pid)"
