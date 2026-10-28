#!/usr/bin/env bash
source "${XDG_CONFIG_HOME:-$HOME/.config}/i3/defaults.conf" 2>/dev/null
fm="${1:-${files:-thunar}}"
if command -v "${fm%% *}" >/dev/null; then exec $fm; fi
for alt in thunar nautilus pcmanfm dolphin nemo; do command -v $alt >/dev/null && exec $alt; done
notify-send -u critical "File manager" "none found"
