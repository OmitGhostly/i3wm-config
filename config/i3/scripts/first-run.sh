#!/usr/bin/env bash
# Runs at every login; does real work only once (seeds colors + wallpaper).
cfg="${XDG_CONFIG_HOME:-$HOME/.config}"; flag="${XDG_CACHE_HOME:-$HOME/.cache}/i3/first-run-done"
[ -e "$flag" ] && exit 0
mkdir -p "$(dirname "$flag")" "$HOME/Pictures/Screenshots"
sleep 2
# start on the night street-lights photo (it suits the black bar); any wallpaper if it is not there
first="${WALL_DIR:-$HOME/Pictures/wallpapers}/night-streetlights.jpg"
if [ -f "$first" ]; then "$cfg/i3/scripts/Wallpaper.sh" --set "$first"; else "$cfg/i3/scripts/Wallpaper.sh" --random; fi
touch "$flag"
