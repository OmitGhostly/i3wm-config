#!/usr/bin/env bash
# Runs at every login; does real work only once (seeds colors + wallpaper).
cfg="${XDG_CONFIG_HOME:-$HOME/.config}"; flag="${XDG_CACHE_HOME:-$HOME/.cache}/i3/first-run-done"
[ -e "$flag" ] && exit 0
mkdir -p "$(dirname "$flag")" "$HOME/Pictures/Screenshots"
sleep 2
"$cfg/i3/scripts/Wallpaper.sh" --random
touch "$flag"
