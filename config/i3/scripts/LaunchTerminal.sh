#!/usr/bin/env bash
# Open the terminal from defaults.conf; if it is not installed, fall back to the next one that is.
source "${XDG_CONFIG_HOME:-$HOME/.config}/i3/defaults.conf" 2>/dev/null
want="${1:-${term:-ghostty}}"
for t in "$want" ghostty kitty alacritty xterm; do
  if command -v "${t%% *}" >/dev/null 2>&1; then exec $t; fi
done
notify-send -u critical "Terminal" "No terminal found (tried $want, ghostty, kitty, alacritty, xterm)" 2>/dev/null
exit 1
